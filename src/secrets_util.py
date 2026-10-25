"""Read an API key without crashing when no secrets file exists.

Streamlit raises an error if code reads st.secrets and there is no secrets.toml (for example,
anyone running the app from a fresh clone). Every key falls back to an environment variable,
then to the default, so the app runs without keys and simply skips TMDB, OMDb, and streaming data.
"""
import os


def safe_secret(name, default=""):
    try:
        import streamlit as st
        return st.secrets.get(name, os.environ.get(name, default))
    except Exception:
        return os.environ.get(name, default)
