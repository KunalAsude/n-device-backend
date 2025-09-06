from pydantic import BaseModel, Field
from typing import Optional

class UserModel(BaseModel):
	user_id: str
	full_name: str
	phone: str
	id: Optional[str] = Field(alias="_id")
