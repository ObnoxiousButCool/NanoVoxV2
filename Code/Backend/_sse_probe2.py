"""Can TestClient read a stream fed by a *separate* background task?"""
import asyncio, threading
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

app = FastAPI()
queue: asyncio.Queue = asyncio.Queue()
gate = threading.Event()


@app.post("/start")
async def start():
    async def work():
        for i in range(3):
            while not gate.is_set():
                await asyncio.sleep(0.01)
            await queue.put(f"item-{i}")
        await queue.put("done")
    app.state.task = asyncio.create_task(work())
    return {"ok": True}


@app.get("/s")
async def stream():
    async def gen():
        yield "data: snapshot\n\n"
        while True:
            item = await queue.get()
            yield f"data: {item}\n\n"
            if item == "done":
                return
    return StreamingResponse(gen(), media_type="text/event-stream")


with TestClient(app) as c:
    gate.clear()
    c.post("/start")
    got = []
    with c.stream("GET", "/s") as r:
        lines = r.iter_lines()
        for ln in lines:
            if ln.startswith("data:"):
                got.append(ln)
                break
        gate.set()
        for ln in lines:
            if ln.startswith("data:"):
                got.append(ln)
                if ln.endswith("done"):
                    break
    print("received:", got)
