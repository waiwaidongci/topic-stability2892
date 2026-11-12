from pydantic import BaseModel,Field
class ComparisonInput(BaseModel):
 run_a_id:int=Field(gt=0)
 run_b_id:int=Field(gt=0)
 name:str=Field(min_length=1,max_length=100)
 threshold:float=Field(ge=0.0,le=0.95,allow_inf_nan=False)
