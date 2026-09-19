import uuid
from typing import Optional, Dict, Any
from fastapi import HTTPException, status

class AppBaseException(HTTPException):
    def __init__(
        self,
        status_code: int,
        user_message: str,
        internal_code: str,
        details: Optional[Dict[str, Any]] = None,
        reference_id: Optional[str] = None
    ):
        ref = reference_id or f"KH-{uuid.uuid4().hex[:6].upper()}"
        super().__init__(
            status_code=status_code,
            detail={
                "error": True,
                "message": user_message,
                "code": internal_code,
                "reference_id": ref,
                "details": details or {}
            }
        )
        self.reference_id = ref
        self.internal_code = internal_code
        self.user_message = user_message

class InvalidPDFException(AppBaseException):
    def __init__(self, message: str = "We could not read this PDF. Please ensure it is a valid bank-generated statement.", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            user_message=message,
            internal_code="ERR_INVALID_PDF",
            details=details
        )

class PasswordProtectedPDFException(AppBaseException):
    def __init__(self, message: str = "This PDF statement is password-protected. Please provide the statement password to proceed."):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            user_message=message,
            internal_code="ERR_PDF_PASSWORD_REQUIRED"
        )

class QuotaExceededException(AppBaseException):
    def __init__(self, remaining: int, requested: int):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            user_message=f"You have only {remaining} pages remaining today. This PDF contains {requested} pages. Please try again tomorrow or request an unlimited account.",
            internal_code="ERR_QUOTA_EXCEEDED",
            details={"remaining_pages": remaining, "requested_pages": requested}
        )

class UnsupportedBankException(AppBaseException):
    def __init__(self, bank_name: Optional[str] = None):
        msg = f"Bank statement format for '{bank_name}' is not supported yet." if bank_name else "We could not identify the statement format for this bank."
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            user_message=msg,
            internal_code="ERR_UNSUPPORTED_BANK_FORMAT"
        )

class ParsingFailedException(AppBaseException):
    def __init__(self, reason: str = "Failed to parse bank statement rows."):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            user_message=f"We could not extract transactions accurately from this PDF. Reason: {reason}",
            internal_code="ERR_PARSING_FAILED"
        )

class XMLGenerationException(AppBaseException):
    def __init__(self, reason: str):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            user_message=f"Tally XML could not be generated safely. Reason: {reason}",
            internal_code="ERR_XML_GENERATION_FAILED"
        )
