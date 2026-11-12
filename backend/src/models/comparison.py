from sqlalchemy.orm import Mapped,mapped_column
from sqlalchemy import String,JSON,ForeignKey,DateTime,UniqueConstraint
from datetime import datetime,timezone
from src.config.database import Base
class TopicComparison(Base):
 __tablename__='topic_comparisons'
 __table_args__=(UniqueConstraint('run_a_id','run_b_id'),)
 id:Mapped[int]=mapped_column(primary_key=True)
 # 两个任务按 id 升序落库，保证 (A,B) 与 (B,A) 是同一条对比；展示侧再命名左右。
 run_a_id:Mapped[int]=mapped_column(ForeignKey('topic_runs.id'))
 run_b_id:Mapped[int]=mapped_column(ForeignKey('topic_runs.id'))
 name:Mapped[str]=mapped_column(String(100))
 threshold:Mapped[float]=mapped_column()
 rule_version:Mapped[str]=mapped_column(String(60))
 result:Mapped[dict]=mapped_column(JSON,default=dict)
 creator_id:Mapped[int]=mapped_column(ForeignKey('users.id'))
 created_at:Mapped[datetime]=mapped_column(DateTime,default=lambda:datetime.now(timezone.utc))
 updated_at:Mapped[datetime]=mapped_column(DateTime,default=lambda:datetime.now(timezone.utc),onupdate=lambda:datetime.now(timezone.utc))
