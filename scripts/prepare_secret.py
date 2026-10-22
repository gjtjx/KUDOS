"""Prepare an ignored raw-key file for Docker/Kubernetes without printing the value."""
import argparse
from pathlib import Path
from dotenv import dotenv_values

def prepare(source, destination):
    values = dotenv_values(source)
    key = (values.get("LLM_API_KEY") or values.get("POE_API_KEY") or "").strip()
    if not key:
        raise ValueError("No API key found in the supplied local settings file")
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Exclusive creation prevents overwriting another deployment's credentials.
    with destination.open("x", encoding="utf-8") as stream:
        stream.write(key)
    destination.chmod(0o600)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    parser.add_argument("--output", type=Path, default=Path(".secrets/llm_api_key"))
    args = parser.parse_args()
    try:
        prepare(args.env_file, args.output)
    except (OSError, ValueError):
        raise SystemExit("Secret file was not prepared. Check the input key and whether the destination already exists.")
    print("Secret file prepared. The credential value has not been printed.")

if __name__ == "__main__":
    main()
