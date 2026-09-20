from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True

    app_name: str = "OC P13 API"
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = ["http://localhost:4200"]
    lichess_explorer_url: str = "https://explorer.lichess.ovh"
    lichess_database: str = "masters"
    lichess_timeout: float = 5.0
    lichess_top_moves: int = 12
    # Jeton personnel Lichess :  https://lichess.org/account/oauth/token
    lichess_token: str = ""
    stockfish_path: str = "stockfish"
    stockfish_depth: int = 15
    stockfish_timeout: float = 8.0

    milvus_host: str = "milvus"
    milvus_port: int = 19530
    milvus_collection: str = "chess_openings"
    milvus_timeout: float = 10.0
    embedding_model: str = "Qwen/Qwen3-Embedding-0.6B"
    embedding_dim: int = 1024
    rag_chunk_size: int = 1400
    rag_chunk_overlap: int = 250
    rag_top_k: int = 4
    wikichess_data_dir: str = "app/data/wikichess"

    # Cle API YouTube Data v3 
    youtube_api_key: str = ""
    youtube_max_results: int = 5
    youtube_min_view_count: int = 0
    youtube_timeout: float = 5.0

    # Cle API Mistral 
    mistral_api_key: str = ""
    mistral_model: str = "open-mistral-nemo"
    mistral_timeout: float = 20.0


settings = Settings()
