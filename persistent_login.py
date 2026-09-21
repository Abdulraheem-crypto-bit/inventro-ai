from pathlib import Path

import streamlit.components.v1 as components

_COMPONENT = components.declare_component(
    "persistent_login",
    path=str(Path(__file__).parent / "persistent_login_component"),
)


def persistent_login(token: str = "", clear: bool = False) -> str:
    value = _COMPONENT(token=token, clear=clear, default="")
    return value if isinstance(value, str) else ""
