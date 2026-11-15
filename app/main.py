import base64
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from app.i18n import normalize_language, tr
from app.presets import DEMO_PRESETS
from app.schemas import (
    ChatAgentRequest,
    ExplainRequest,
    Form8843Request,
    ResidencyRequest,
    ResidencyResponse,
    TaxCalculationRequest,
    TaxCalculationResponse,
    TransactionsAnalyzeRequest,
    TransactionsAnalyzeResponse,
    UnifiedAnalyzeRequest,
    copy_model,
    dump_model,
)
from app.services.advisor import f1_self_employment_note, generate_explanation, run_chat_turn
from app.services.pdf_8843 import generate_form_8843_pdf
from app.services.residency import calculate_residency
from app.services.taxes import calculate_taxes
from app.services.transactions import analyze_transactions

app = FastAPI(title="ARATax API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
@app.get("/api/health")
def health_check() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "ARATax US Tax & Residency API",
        "subscription": {
            "active": True,
            "tier": "Filing Pack Pro",
            "features_unlocked": [
                "substantial_presence_test_engine",
                "form_8843_pdf_generator",
                "1099_and_w2_hybrid_tax_calculator",
                "fica_refund_detector",
                "bank_statement_deduction_finder",
                "ai_plain_language_explainer",
            ],
        },
        "endpoints": [
            "GET  /api/health",
            "GET  /api/demo-presets",
            "POST /api/residency/calculate",
            "POST /api/taxes/calculate",
            "POST /api/transactions/analyze",
            "POST /api/form-8843/pdf",
            "POST /api/form-8843/base64",
            "POST /api/explain",
            "POST /api/analyze-all",
            "POST /api/chat",
        ],
    }


@app.get("/api/demo-presets")
def get_demo_presets(language: str = "en") -> Dict[str, Any]:
    lang = normalize_language(language)
    presets = [
        {
            **preset,
            "title": tr(lang, f"preset_{preset['preset_id']}_title"),
            "subtitle": tr(lang, f"preset_{preset['preset_id']}_subtitle"),
        }
        for preset in DEMO_PRESETS
    ]
    return {"count": len(presets), "language": lang, "presets": presets}


@app.post("/api/residency/calculate", response_model=ResidencyResponse)
def residency_endpoint(req: ResidencyRequest) -> ResidencyResponse:
    try:
        return calculate_residency(req)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/taxes/calculate", response_model=TaxCalculationResponse)
def taxes_endpoint(req: TaxCalculationRequest) -> TaxCalculationResponse:
    try:
        return calculate_taxes(req)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/transactions/analyze", response_model=TransactionsAnalyzeResponse)
def transactions_endpoint(req: TransactionsAnalyzeRequest) -> TransactionsAnalyzeResponse:
    try:
        return analyze_transactions(req)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/form-8843/pdf")
def form_8843_pdf_endpoint(req: Form8843Request) -> Response:
    pdf_bytes = generate_form_8843_pdf(req)
    filename = f"IRS_Form_8843_{req.tax_year}_{req.last_name}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.post("/api/form-8843/base64")
def form_8843_base64_endpoint(req: Form8843Request) -> Dict[str, Any]:
    pdf_bytes = generate_form_8843_pdf(req)
    filename = f"IRS_Form_8843_{req.tax_year}_{req.last_name}.pdf"
    return {
        "filename": filename,
        "mime_type": "application/pdf",
        "size_bytes": len(pdf_bytes),
        "pdf_base64": base64.b64encode(pdf_bytes).decode("ascii"),
    }


@app.post("/api/explain")
def explain_endpoint(req: ExplainRequest) -> Dict[str, Any]:
    return generate_explanation(req)


@app.post("/api/chat")
def chat_endpoint(req: ChatAgentRequest) -> Dict[str, Any]:
    try:
        return run_chat_turn(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/analyze-all")
def analyze_all_endpoint(req: UnifiedAnalyzeRequest) -> Dict[str, Any]:
    try:
        return _analyze_all(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _analyze_all(req: UnifiedAnalyzeRequest) -> Dict[str, Any]:
    res_out = calculate_residency(copy_model(req.residency, {"language": req.language}))
    tx_out: Optional[TransactionsAnalyzeResponse] = (
        analyze_transactions(copy_model(req.transactions, {"language": req.language}))
        if req.transactions
        else None
    )

    tax_out: Optional[TaxCalculationResponse] = None
    if req.taxes:
        ded = req.taxes.business_deductions
        inc_1099 = req.taxes.gross_1099_income
        if tx_out:
            if ded == 0.0 and tx_out.total_deductible_expenses > 0:
                ded = tx_out.total_deductible_expenses
            if inc_1099 == 0.0 and tx_out.total_income_1099 > 0:
                inc_1099 = tx_out.total_income_1099

        synced = copy_model(
            req.taxes,
            {
                "residency_status": res_out.residency_status,
                "gross_1099_income": inc_1099,
                "business_deductions": ded,
                "language": req.language,
            },
        )
        tax_out = calculate_taxes(synced)

    form_8843: Optional[Dict[str, Any]] = None
    if req.form_8843_profile and res_out.exempt_individual_active:
        pdf_bytes = generate_form_8843_pdf(req.form_8843_profile)
        form_8843 = {
            "filename": f"IRS_Form_8843_{req.form_8843_profile.tax_year}_{req.form_8843_profile.last_name}.pdf",
            "mime_type": "application/pdf",
            "pdf_base64": base64.b64encode(pdf_bytes).decode("ascii"),
        }

    explanation = generate_explanation(
        ExplainRequest(
            language=req.language,
            residency_result=dump_model(res_out),
            tax_result=dump_model(tax_out) if tax_out else None,
        )
    )

    advisories = []
    if req.taxes:
        note = f1_self_employment_note(req.language, req.taxes.visa_type, req.taxes.gross_1099_income)
        if note:
            advisories.append(note)

    return {
        "subscription_active": True,
        "advisories": advisories,
        "residency": dump_model(res_out),
        "transactions": dump_model(tx_out) if tx_out else None,
        "taxes": dump_model(tax_out) if tax_out else None,
        "form_8843": form_8843,
        "ai_explanation": explanation,
    }
