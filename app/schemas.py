from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def dump_model(model: BaseModel) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def copy_model(model: BaseModel, update: Dict[str, Any]) -> Any:
    if hasattr(model, "model_copy"):
        return model.model_copy(update=update)
    return model.copy(update=update)


class VisaStay(BaseModel):
    visa_type: str
    entry_date: str
    exit_date: str


class ResidencyRequest(BaseModel):
    tax_year: int = 2025
    stays: List[VisaStay] = Field(default_factory=list)
    prior_exempt_calendar_years: List[int] = Field(default_factory=list)
    has_green_card: bool = False
    country_of_citizenship: str = "Kazakhstan"
    closer_connection_eligible: bool = False


class YearDayBreakdown(BaseModel):
    year: int
    total_physical_days: int
    exempt_days: int
    countable_days: int
    weight: float
    weighted_countable_days: float
    exempt_reason: Optional[str] = None


class FilingFormItem(BaseModel):
    form_code: str
    title: str
    mandatory: bool
    deadline: str
    reason: str
    official_url: str


class ResidencyResponse(BaseModel):
    tax_year: int
    residency_status: str
    status_label: str
    meets_substantial_presence_test: bool
    meets_green_card_test: bool
    current_year_countable_days: int
    total_weighted_days: float
    spt_threshold_days: int = 183
    exempt_individual_active: bool
    exempt_years_used_prior_to_tax_year: int
    year_breakdown: List[YearDayBreakdown]
    dual_status_detected: bool
    first_year_choice_available: bool
    fica_exempt_status: bool
    india_treaty_standard_deduction_eligible: bool
    filing_plan: List[FilingFormItem]
    software_warnings: List[str]
    irs_citations: List[Dict[str, str]]


class TransactionInput(BaseModel):
    id: Optional[str] = None
    date: str = "2025-06-15"
    description: str
    amount: float
    type_hint: Optional[str] = None


class CategorizedTransaction(BaseModel):
    id: str
    date: str
    description: str
    amount: float
    classification: str
    schedule_c_category: Optional[str] = None
    deductible_percentage: float = 0.0
    deductible_amount: float = 0.0
    estimated_tax_saved: float = 0.0
    reason: str


class TransactionsAnalyzeRequest(BaseModel):
    tax_year: int = 2025
    marginal_tax_rate_estimate: float = 0.273
    transactions: List[TransactionInput] = Field(default_factory=list)
    csv_text: Optional[str] = None
    use_ai: bool = True


class TransactionsAnalyzeResponse(BaseModel):
    total_income_1099: float
    total_business_expenses_raw: float
    total_deductible_expenses: float
    total_personal_expenses: float
    estimated_total_tax_savings: float
    category_summary: Dict[str, float]
    transactions: List[CategorizedTransaction]


class TaxCalculationRequest(BaseModel):
    tax_year: int = 2025
    filing_status: str = "single"
    residency_status: str = "RESIDENT_ALIEN"
    visa_type: str = "H-1B"
    country_of_citizenship: str = "Kazakhstan"
    gross_1099_income: float = Field(0.0, ge=0.0)
    business_deductions: float = Field(0.0, ge=0.0)
    w2_wages: float = Field(0.0, ge=0.0)
    w2_federal_withheld: float = Field(0.0, ge=0.0)
    w2_fica_withheld: float = Field(0.0, ge=0.0)
    estimated_payments_already_made: float = Field(0.0, ge=0.0)


class BracketBreakdownItem(BaseModel):
    rate_percent: float
    bracket_floor: float
    bracket_ceiling: Optional[float]
    taxable_in_bracket: float
    tax_amount: float


class QuarterlyPaymentItem(BaseModel):
    quarter: str
    period: str
    due_date: str
    amount_due: float


class TaxCalculationResponse(BaseModel):
    tax_year: int
    residency_status: str
    filing_status: str
    gross_total_income: float
    net_self_employment_income: float
    self_employment_tax: float
    se_tax_deductible_half: float
    se_tax_exempt_nonresident: bool
    adjusted_gross_income: float
    standard_deduction_applied: float
    qbi_deduction_applied: float
    taxable_income: float
    federal_income_tax: float
    total_tax_liability: float
    effective_tax_rate_percent: float
    Deduction_tax_savings_usd: float
    w2_federal_withheld: float
    erroneous_fica_refund_amount: float
    erroneous_fica_explanation: Optional[str] = None
    net_tax_owed_or_refund: float
    is_refund: bool
    recommended_monthly_set_aside: float
    quarterly_schedule: List[QuarterlyPaymentItem]
    bracket_breakdown: List[BracketBreakdownItem]
    irs_direct_pay_url: str = "https://www.irs.gov/payments/direct-pay"
    filing_status_note: str


class Form8843Request(BaseModel):
    tax_year: int = 2025
    first_name: str = "Ali"
    last_name: str = "Abylgazy"
    us_address: str = "500 El Camino Real, Stanford, CA 94305"
    home_country_address: str = "Astana, Kazakhstan"
    visa_type: str = "F-1"
    current_nonimmigrant_status: str = "F-1 Student (OPT)"
    country_of_citizenship: str = "Kazakhstan"
    country_of_passport: str = "Kazakhstan"
    passport_number: str = "N12345678"
    first_entry_date: str = "2023-08-20"
    days_present_current_year: int = Field(365, ge=0, le=366)
    days_present_prior_year_1: int = Field(365, ge=0, le=366)
    days_present_prior_year_2: int = Field(134, ge=0, le=366)
    days_excluded_current_year: int = Field(365, ge=0, le=366)
    is_student: bool = True
    school_or_program_name: str = "Stanford University"
    school_or_program_address: str = "450 Jane Stanford Way, Stanford, CA 94305"
    school_or_program_phone: str = "(650) 723-2300"
    director_or_dso_name: str = "Jane Smith, Designated School Official (DSO)"
    director_or_dso_Address: str = "Bechtel International Center, Stanford, CA 94305"
    director_or_dso_phone: str = "(650) 723-1831"


class ExplainRequest(BaseModel):
    language: str = "ru"
    residency_result: Optional[Dict[str, Any]] = None
    tax_result: Optional[Dict[str, Any]] = None
    user_question: Optional[str] = None


class UnifiedAnalyzeRequest(BaseModel):
    residency: ResidencyRequest
    taxes: Optional[TaxCalculationRequest] = None
    transactions: Optional[TransactionsAnalyzeRequest] = None
    form_8843_profile: Optional[Form8843Request] = None
    language: str = "ru"


class ChatMessage(BaseModel):
    role: str
    content: str


class CollectedTaxProfile(BaseModel):
    tax_year: int = 2025
    visa_type: Optional[str] = None
    entry_date: Optional[str] = None
    country_of_citizenship: Optional[str] = None
    gross_1099_income: Optional[float] = None
    business_deductions: Optional[float] = None
    w2_wages: Optional[float] = None
    w2_federal_withheld: Optional[float] = None
    w2_fica_withheld: Optional[float] = None


class ChatAgentRequest(BaseModel):
    messages: List[ChatMessage] = Field(default_factory=list)
    collected_profile: Optional[CollectedTaxProfile] = None
    language: str = "ru"
