"""ASGI entrypoint."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run("invesbao.api.app:app", host="0.0.0.0", port=8000, reload=True)
