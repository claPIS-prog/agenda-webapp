from pydantic import BaseModel
from typing import Optional

class AmicoPayload(BaseModel):
    telegram_id: int
    password: str
    nome: str

class PermessiPayload(BaseModel):
    user_id: int
    permessi: dict
    dati: dict
    data_inizio_validita: Optional[str] = None
    data_revoca: Optional[str] = None
    data_fine_validita: Optional[str] = None

class AzionePayload(BaseModel):
    dati: dict

class RinnovoPayload(BaseModel):
    dati: dict

class ListaPayload(BaseModel):
    nome: str
    tabella: str

class OperatorePayload(BaseModel):
    dati: dict

class NotaPayload(BaseModel):
    dati: dict

class CredenzialiPayload(BaseModel):
    dati: dict

class CalcoloPayload(BaseModel):
    dati: dict

class CreditoPayload(BaseModel):
    dati: dict
