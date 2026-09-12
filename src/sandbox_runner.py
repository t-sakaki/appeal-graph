"""Daytonaサンドボックス内でコードを安全に実行・検証する最小実装。"""
import os
from daytona import Daytona, DaytonaConfig
from dotenv import load_dotenv

load_dotenv()


class SandboxRunner:
    def __init__(self):
        config = DaytonaConfig(
            api_key=os.environ["DAYTONA_API_KEY"],
            api_url=os.environ.get("DAYTONA_API_URL"),
        )
        self.daytona = Daytona(config)
        self.sandbox = None

    def start(self):
        self.sandbox = self.daytona.create()
        return self.sandbox

    def run_code(self, code: str) -> dict:
        """サンドボックス内でPythonコードを実行し、結果を返す。"""
        if self.sandbox is None:
            self.start()
        response = self.sandbox.process.code_run(code)
        return {
            "exit_code": response.exit_code,
            "result": response.result,
        }

    def cleanup(self):
        if self.sandbox:
            self.daytona.delete(self.sandbox)
            self.sandbox = None


if __name__ == "__main__":
    runner = SandboxRunner()
    try:
        out = runner.run_code("print('hello from daytona sandbox')")
        print(out)
    finally:
        runner.cleanup()
