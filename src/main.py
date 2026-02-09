from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from docxtpl import DocxTemplate
import io
import asyncio
import logging

from src.services import NamePayload

try:
    from sanctions.parserEU import SanctionsEU
    from sanctions.parserOFAC import ParserOFAC as OfacParser
    from sanctions.parserUK import ParserUK as UkParser
    from sanctions.parserUN import ParserUN as UnParser
    SANCTIONS_AVAILABLE = True
except ImportError as e:  # pragma: no cover
    # Fallback dummy parsers for environments without the sanctions package
    logger.warning(f"Sanctions parsers are not available: {e}")
    
    class _MissingSanctions:
        def __init__(self, *args, **kwargs):
            raise NotImplementedError("Sanctions parsers are not available in this environment.")

    SanctionsEU = OfacParser = UkParser = UnParser = _MissingSanctions
    SANCTIONS_AVAILABLE = False


# Настройка логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


app = FastAPI(
    title="Sanctions & Templates API",
    description="API для проверки санкций и заполнения DOCX-шаблонов через Jinja.",
    version="1.0.0",
)


@app.get("/healthz")
async def health_check():
    """Health check endpoint for deployment platforms."""
    return {"status": "healthy", "service": "sanctions-templates-api"}


@app.post("/sanctions/eu")
async def check_sanctions_eu(payload: NamePayload):
    full_name = payload.name.strip()
    parser = SanctionsEU()
    found, content, filename, media_type = await asyncio.to_thread(parser.fetch, full_name)
    return StreamingResponse(
        io.BytesIO(content),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "found": "true" if found else "false",
            "Access-Control-Expose-Headers": "found",
        },
    )


@app.post("/sanctions/ofac")
async def check_sanctions_ofac(payload: NamePayload):
    full_name = payload.name.strip()
    parser = OfacParser()
    found, content, filename, media_type = await asyncio.to_thread(parser.fetch, full_name)
    return StreamingResponse(
        io.BytesIO(content),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "found": "true" if found else "false",
            "Access-Control-Expose-Headers": "found",
        },
    )


@app.post("/sanctions/uk")
async def check_sanctions_uk(payload: NamePayload):
    full_name = payload.name.strip()
    parser = UkParser()
    found, content, filename, media_type = await asyncio.to_thread(parser.fetch, full_name)
    return StreamingResponse(
        io.BytesIO(content),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "found": "true" if found else "false",
            "Access-Control-Expose-Headers": "found",
        },
    )


@app.post("/sanctions/un")
async def check_sanctions_un(payload: NamePayload):
    full_name = payload.name.strip()
    parser = UnParser()
    found, content, filename, media_type = await asyncio.to_thread(parser.fetch, full_name)
    return StreamingResponse(
        io.BytesIO(content),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "found": "true" if found else "false",
            "Access-Control-Expose-Headers": "found",
        },
    )


@app.post("/fill-natural")
async def fill_natural_doc(form: dict):
    input_template = "./templates/Person Jinja.docx"
    doc = DocxTemplate(input_template)

    if "properties" in form:
        form = form["properties"]

    output_path = "filled_form.docx"
    doc.render(form)
    doc.save(output_path)

    return FileResponse(
        output_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="filled.docx",
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=False)
