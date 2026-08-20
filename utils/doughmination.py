import aiohttp

profileBase = "https://doughmination.uk/v2/discord"
genshinBase = "https://doughmination.uk/v2/genshin"


class DoughminationError(Exception):
    pass


class ProfileNotFoundError(DoughminationError):
    pass


class GenshinNotFoundError(DoughminationError):
    pass


class DoughminationAPI:
    """Shared client for the Doughmination public API endpoints. One session
    is reused across every cog that talks to doughmination.uk, so call
    `close()` once during bot shutdown rather than per-cog."""

    def __init__(self) -> None:
        self._session: aiohttp.ClientSession | None = None

    def _getSession(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()

    async def _get(self, url: str, notFoundError: type[DoughminationError]) -> dict:
        session = self._getSession()
        async with session.get(url) as resp:
            body = await resp.json()
            if not body.get("success") or body.get("data") is None:
                error = body.get("error") or {}
                message = error.get("message", "Unknown API error")
                if resp.status == 404 or error.get("code") == "not_found":
                    raise notFoundError(message)
                raise RuntimeError(f"Doughmination API error: {message}")
            return body["data"]

    # --- Discord profile (/v2/discord) ---

    async def getProfile(self, userId: int) -> dict:
        return await self._get(f"{profileBase}/users/{userId}", ProfileNotFoundError)

    # --- Genshin roster (/v2/genshin) ---

    async def getGenshinRoster(self, uid: str) -> dict:
        return await self._get(f"{genshinBase}/roster/{uid}", GenshinNotFoundError)

    async def getGenshinCharacter(self, uid: str, heroId: str) -> dict:
        return await self._get(f"{genshinBase}/roster/{uid}/{heroId}", GenshinNotFoundError)


dough = DoughminationAPI()
