"""Fail image builds if the installed password backend cannot hash and verify."""
from importlib.metadata import version

from passlib.context import CryptContext


def main():
    installed = {name: version(name) for name in ("passlib", "bcrypt")}
    print(f"Password backend versions: {installed}", flush=True)
    if installed != {"passlib": "1.7.4", "bcrypt": "4.0.1"}:
        raise RuntimeError("Password backend does not match the tested dependency pins")
    context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    for password in ("build-check-password", "a" * 72, "\u00e9" * 36):
        hashed = context.hash(password)
        if not context.verify(password, hashed):
            raise RuntimeError("Password verification failed")
        if context.verify("incorrect-password", hashed):
            raise RuntimeError("Incorrect password accepted")
    print("Password backend check passed", flush=True)


if __name__ == "__main__":
    main()
