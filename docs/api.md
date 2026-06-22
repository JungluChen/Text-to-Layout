# API Generation

Generate API documentation from public modules with:

```powershell
py -3 -m uv run python -c "from text_to_gds.platform_extensions import generate_api_documentation; import text_to_gds.scientific_verification as m; print(generate_api_documentation([m.run_full_verification]))"
```
