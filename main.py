import httpx
import feedparser
from fastapi import FastAPI, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional

# -- Metadata cho API Docs --
# (Thông tin này sẽ hiển thị trên giao diện Swagger UI tự động của FastAPI)
app_metadata = {
    "title": "Vietnam Investing News API",
    "description": "API tổng hợp tin tức từ các RSS feed của vn.investing.com. \nCung cấp dữ liệu về Phân tích cơ bản, kỹ thuật, ý kiến chuyên gia và ý tưởng đầu tư.",
    "version": "1.0.0",
    "contact": {
        "name": "Tên của bạn",
        "url": "https://github.com/your-username", # Thay bằng link GitHub của bạn
    },
}

app = FastAPI(**app_metadata)

# -- Cấu hình CORS (Cross-Origin Resource Sharing) --
# Cho phép tất cả các nguồn gốc (domains) có thể gọi tới API này.
# Trong môi trường production, bạn nên giới hạn lại chỉ những domain được phép.
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# -- Định nghĩa các nguồn RSS --
# Sử dụng một dictionary để quản lý các feed, giúp code sạch sẽ và dễ mở rộng.
RSS_FEEDS = {
    "fundamental": "https://vn.investing.com/rss/market_overview_Fundamental.rss",
    "technical": "https://vn.investing.com/rss/market_overview_Technical.rss",
    "opinion": "https://vn.investing.com/rss/market_overview_Opinion.rss",
    "ideas": "https://vn.investing.com/rss/market_overview_investing_ideas.rss",
}

# -- Định nghĩa cấu trúc dữ liệu trả về bằng Pydantic --
# Giúp validate dữ liệu và tự động sinh ra JSON schema cho API docs.
class NewsItem(BaseModel):
    title: str = Field(..., description="Tiêu đề bài viết")
    link: str = Field(..., description="Đường dẫn tới bài viết gốc")
    published: str = Field(..., description="Thời gian xuất bản")
    summary: Optional[str] = Field(None, description="Tóm tắt nội dung bài viết")
    
    class Config:
        # Cấu hình để Pydantic có thể làm việc với các đối tượng Python
        from_attributes = True


class ApiResponse(BaseModel):
    category: str = Field(..., description="Chuyên mục tin tức")
    source: str = Field(..., description="Nguồn RSS được sử dụng")
    items: List[NewsItem] = Field(..., description="Danh sách các tin bài")


# -- Endpoint của API --
@app.get(
    "/api/v1/news/{category}",
    response_model=ApiResponse,
    summary="Lấy tin tức theo chuyên mục",
    tags=["News"]
)
async def get_news_by_category(
    category: str = Path(..., description=f"Chuyên mục tin tức. Các giá trị hợp lệ: {', '.join(RSS_FEEDS.keys())}")
):
    """
    Endpoint này nhận vào một **chuyên mục** và trả về danh sách các tin bài mới nhất từ RSS feed tương ứng của vn.investing.com.

    - **category**: Tên chuyên mục bạn muốn lấy tin.
    """
    if category not in RSS_FEEDS:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "Category not found",
                "available_categories": list(RSS_FEEDS.keys())
            }
        )

    feed_url = RSS_FEEDS[category]

    try:
        # Sử dụng httpx.AsyncClient để gửi request bất đồng bộ
        async with httpx.AsyncClient() as client:
            response = await client.get(feed_url, timeout=10.0)
            response.raise_for_status()  # Ném lỗi nếu request không thành công (status code 4xx hoặc 5xx)

        # Phân tích cú pháp RSS feed bằng feedparser
        parsed_feed = feedparser.parse(response.text)

        if parsed_feed.bozo:
             # 'bozo' là cờ báo hiệu feed có thể không đúng chuẩn XML
            print(f"Warning: Feed for '{category}' may be malformed. Reason: {parsed_feed.bozo_exception}")

        # Chuyển đổi dữ liệu sang cấu trúc Pydantic đã định nghĩa
        news_items = [
            NewsItem(
                title=entry.title,
                link=entry.link,
                published=entry.published,
                summary=entry.summary if 'summary' in entry else None
            ) for entry in parsed_feed.entries
        ]

        return ApiResponse(
            category=category,
            source=feed_url,
            items=news_items
        )

    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Service Unavailable: Could not fetch data from RSS feed. Reason: {e}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Internal Server Error: An unexpected error occurred. Reason: {str(e)}"
        )


@app.get("/", include_in_schema=False)
def root():
    return {"message": "Welcome to the Vietnam Investing News API. Go to /docs to see the API documentation."}

