"""Add doctor credential fields, private documents and password reset tokens.
Revision ID: 91c2a4f7d8e1
Revises: 4e37299b4b21
"""
from alembic import op
import sqlalchemy as sa

revision = "91c2a4f7d8e1"
down_revision = "4e37299b4b21"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("doctors", sa.Column("graduation_year", sa.Integer(), nullable=True))
    op.add_column("doctors", sa.Column("medical_college", sa.String(length=200), nullable=True))
    op.add_column("doctors", sa.Column("previous_workplaces", sa.Text(), nullable=True))
    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_password_reset_tokens_user_id", "password_reset_tokens", ["user_id"])
    op.create_index("ix_password_reset_tokens_token_hash", "password_reset_tokens", ["token_hash"], unique=True)
    op.create_index("ix_password_reset_tokens_expires_at", "password_reset_tokens", ["expires_at"])
    op.create_table(
        "doctor_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("doctor_id", sa.Integer(), sa.ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_type", sa.String(80), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("stored_filename", sa.String(255), nullable=False, unique=True),
        sa.Column("content_type", sa.String(120), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_doctor_documents_doctor_id", "doctor_documents", ["doctor_id"])

def downgrade():
    op.drop_index("ix_doctor_documents_doctor_id", table_name="doctor_documents")
    op.drop_table("doctor_documents")
    op.drop_index("ix_password_reset_tokens_expires_at", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_token_hash", table_name="password_reset_tokens")
    op.drop_index("ix_password_reset_tokens_user_id", table_name="password_reset_tokens")
    op.drop_table("password_reset_tokens")
    op.drop_column("doctors", "previous_workplaces")
    op.drop_column("doctors", "medical_college")
    op.drop_column("doctors", "graduation_year")
