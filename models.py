from pydantic import BaseModel

class AmicoPayload(BaseModel):
    telegram_id: int
    password: str
    nome: str

class PermessiPayload(BaseModel):
    user_id: int
    permessi: dict

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