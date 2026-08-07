"""One module per dashboard page, each exposing a `render()` function.

Deliberately not named `pages/`: Streamlit treats a `pages/` directory next to
the entrypoint as an automatic multipage app and would build its own navigation
on top of the sidebar selector.
"""
