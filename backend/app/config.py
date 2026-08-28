from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = True

    app_name: str = "OC P13 API"
    api_prefix: str = "/api/v1"
    lichess_explorer_url: str = "https://explorer.lichess.ovh"
    lichess_database: str = "masters"
    lichess_timeout: float = 5.0
    lichess_top_moves: int = 12
    # Jeton personnel Lichess :  https://lichess.org/account/oauth/token
    lichess_token: str = ""
    stockfish_path: str = "stockfish"
    stockfish_depth: int = 15


settings = Settings()
