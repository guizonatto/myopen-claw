from dotenv import load_dotenv
import os

load_dotenv(dotenv_path='c:/github/myopen-claw/.env')

print("GITHUB_TOKEN:", os.getenv("GITHUB_TOKEN"))
print("GITHUB_REPO:", os.getenv("GITHUB_REPO"))
