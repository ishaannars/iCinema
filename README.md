# iCinema


## Live ratings and metadata

The deployed app can enrich movie cards from OMDb using a private Streamlit secret named `OMDB_API_KEY`.

Displayed IMDb ratings, Rotten Tomatoes scores, genres, runtime, and short plot metadata are cached for **14 days**. After the cache expires, the next request refreshes the title from the source.

Configure the key in Streamlit Community Cloud under **App settings → Secrets**:

```toml
OMDB_API_KEY = "your_key_here"
```

Never commit `.streamlit/secrets.toml` or an API key to GitHub.
