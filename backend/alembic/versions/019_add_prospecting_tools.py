"""add prospecting_tools table with seed data

Revision ID: 019
Revises: 018
Create Date: 2026-03-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '019'
down_revision: Union[str, None] = '018'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'prospecting_tools',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('display_name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('when_to_use', sa.Text(), nullable=True),
        sa.Column('cost_info', sa.String(255), nullable=True),
        sa.Column('sectors_strong', sa.JSON(), nullable=True),
        sa.Column('sectors_weak', sa.JSON(), nullable=True),
        sa.Column('apify_actor_id', sa.String(255), nullable=True),
        sa.Column('output_type', sa.String(50), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name'),
    )

    # Seed data
    op.execute("""
        INSERT INTO prospecting_tools (name, display_name, description, when_to_use, cost_info, sectors_strong, sectors_weak, apify_actor_id, output_type, is_enabled, sort_order)
        VALUES
        (
            'google_maps',
            'Google Maps Scraper',
            'Cerca attivita locali su Google Maps. Ritorna nome, indirizzo, telefono, sito web, rating, categoria.',
            'Fonte PRIMARIA per trovare aziende. Usa sempre come primo step per qualsiasi settore con presenza fisica locale: ristoranti, hotel, negozi, studi professionali, agenzie, artigiani, cliniche. Ottimo per avere subito telefono e sito web.',
            '~$2.10 per 1000 risultati',
            '["horeca", "retail", "servizi locali", "studi professionali", "artigianato", "sanita", "beauty", "automotive"]',
            '["SaaS", "startup tech", "enterprise B2B", "aziende solo online"]',
            'compass/crawler-google-places',
            'companies',
            true,
            1
        ),
        (
            'website_contacts',
            'Website Email/Phone Extractor',
            'Estrae email, telefono e profili social dai siti web trovati.',
            'Usa DOPO Google Maps o quando hai una lista di URL senza contatti diretti. Scansiona il sito fino a 2 livelli di profondita per trovare email (info@, contatti@, etc.), numeri di telefono e link social.',
            '~$0.04 per CU (~gratis)',
            '["tutti i settori con sito web"]',
            '["aziende senza sito web"]',
            'anchor/email-phone-extractor',
            'contacts',
            true,
            2
        ),
        (
            'linkedin_companies',
            'LinkedIn Company Scraper',
            'Scrapa profili LinkedIn aziendali: descrizione, dipendenti, settore, specialita, follower.',
            'Usa per arricchire i dati aziendali con info LinkedIn. Utile per capire dimensione reale, specializzazioni, e positioning. Richiede URL LinkedIn o nome azienda.',
            '~$0.01 per profilo',
            '["B2B", "tech", "servizi professionali", "consulting", "agenzie digitali"]',
            '["micro imprese locali", "artigiani", "attivita senza LinkedIn"]',
            'curious_coder/linkedin-company-scraper',
            'companies',
            true,
            3
        ),
        (
            'linkedin_people',
            'LinkedIn Profile Search',
            'Cerca decision maker su LinkedIn per titolo, azienda, zona. Non richiede cookies.',
            'Usa per trovare i decision maker (CEO, Direttore Commerciale, Marketing Manager, CTO). Ideale per Step 2 del framework. Cerca per ruolo + azienda + zona geografica.',
            '~$0.01 per profilo',
            '["tutti i settori B2B", "management", "C-level"]',
            '["micro imprese senza LinkedIn", "settori poco digitalizzati"]',
            'harvestapi/linkedin-profile-search',
            'people',
            true,
            4
        );
    """)


def downgrade() -> None:
    op.drop_table('prospecting_tools')
