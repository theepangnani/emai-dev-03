from fastapi import FastAPI

app = FastAPI()


def hello_world() -> str:
    return "Hello World"


@app.get("/")
def root():
    return {"message": hello_world()}
