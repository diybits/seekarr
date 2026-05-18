# Seekarr Documentation

This directory contains the official documentation for the Seekarr project, which is automatically published to [https://diybits.github.io/seekarr/](https://diybits.github.io/seekarr/).

## Structure

The documentation is built using GitHub Pages with files directly from the `/docs` folder. The main entry point is `index.html`.

## Contributing

To contribute to the documentation:

1. Make changes to files in the `/docs` directory
2. Submit a pull request to the main branch
3. Once approved and merged, GitHub Actions will automatically deploy the changes

## Local Testing

To test documentation locally, you can use Python's built-in HTTP server:

```bash
cd /path/to/Seekarr/docs
python -m http.server 8000
```

Then open your browser to `http://localhost:8000`.

## Coverage

The docs currently include:

- Installation and quick-setup guides
- Configuration reference
- Integration settings pages for all supported apps (Sonarr, Radarr, Lidarr, Readarr, Whisparr, Whisparr V3/Eros)
- General and app-level settings reference

## Contact

If you have questions about the documentation, please open an issue or start a discussion on GitHub.
