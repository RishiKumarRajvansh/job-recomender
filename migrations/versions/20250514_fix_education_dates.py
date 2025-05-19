"""fix education dates

Revision ID: 20250514_fix_education_dates
Revises: # you'll need to fill this in with your last migration ID
Create Date: 2025-05-14 18:29:00.000000

"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime

# revision identifiers, used by Alembic.
revision = '20250514_fix_education_dates'
down_revision = None  # you'll need to fill this in with your last migration ID
branch_labels = None
depends_on = None

def upgrade():
    # Create temporary columns
    op.add_column('education', sa.Column('start_date_new', sa.DateTime, nullable=True))
    op.add_column('education', sa.Column('end_date_new', sa.DateTime, nullable=True))

    # Get database connection
    connection = op.get_bind()

    # Select all education records
    education = sa.Table(
        'education',
        sa.MetaData(),
        sa.Column('id', sa.Integer),
        sa.Column('start_date', sa.String),
        sa.Column('end_date', sa.String),
        sa.Column('start_date_new', sa.DateTime),
        sa.Column('end_date_new', sa.DateTime),
    )

    # Update records
    for record in connection.execute(sa.select(education)):
        # Convert start_date
        if record.start_date:
            try:
                start_date = datetime.strptime(record.start_date, '%Y-%m-%d %H:%M:%S')
                connection.execute(
                    education.update().
                    where(education.c.id == record.id).
                    values(start_date_new=start_date)
                )
            except (ValueError, TypeError):
                pass

        # Convert end_date
        if record.end_date:
            try:
                end_date = datetime.strptime(record.end_date, '%Y-%m-%d %H:%M:%S')
                connection.execute(
                    education.update().
                    where(education.c.id == record.id).
                    values(end_date_new=end_date)
                )
            except (ValueError, TypeError):
                pass

    # Drop old columns and rename new ones
    op.drop_column('education', 'start_date')
    op.drop_column('education', 'end_date')
    op.alter_column('education', 'start_date_new', new_column_name='start_date')
    op.alter_column('education', 'end_date_new', new_column_name='end_date')

def downgrade():
    # Convert back to string format if needed
    op.alter_column('education', 'start_date',
                    type_=sa.String,
                    postgresql_using="start_date::varchar")
    op.alter_column('education', 'end_date',
                    type_=sa.String,
                    postgresql_using="end_date::varchar")
