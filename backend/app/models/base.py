"""SQLAlchemy declarative base and all ORM model classes.

All tables match REQUIREMENTS.md §11 exactly.
"""

import uuid

from sqlalchemy import (
    CheckConstraint,
    Column,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# 11.1 companies
# ---------------------------------------------------------------------------
class Company(Base):
    __tablename__ = "companies"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    name = Column(Text, nullable=False)
    mission = Column(Text, nullable=True)
    vision = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    search_vector = Column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', coalesce(name,'') || ' ' || coalesce(mission,'') || ' ' || coalesce(vision,''))",
            persisted=True,
        ),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_companies_lower_name", text("lower(name)"), unique=True),
        Index("ix_companies_search_vector", "search_vector", postgresql_using="gin"),
    )

    # Relationships
    functional_areas = relationship("FunctionalArea", back_populates="company", cascade="all, delete-orphan")
    persons = relationship("Person", back_populates="company", cascade="all, delete-orphan")
    sources = relationship("Source", back_populates="company", cascade="all, delete-orphan")
    inferred_facts = relationship("InferredFact", back_populates="company", cascade="all, delete-orphan")
    relationships_list = relationship("Relationship", back_populates="company", cascade="all, delete-orphan")
    action_items = relationship("ActionItem", back_populates="company", cascade="all, delete-orphan")
    generated_documents = relationship("GeneratedDocument", back_populates="company", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# 11.2 functional_areas
# ---------------------------------------------------------------------------
class FunctionalArea(Base):
    __tablename__ = "functional_areas"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    name = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("company_id", "name", name="uq_functional_areas_company_name"),
        Index("ix_functional_areas_company_id", "company_id"),
    )

    company = relationship("Company", back_populates="functional_areas")
    persons = relationship("Person", back_populates="primary_area")
    inferred_facts = relationship("InferredFact", back_populates="functional_area")
    action_items = relationship("ActionItem", back_populates="functional_area")


# ---------------------------------------------------------------------------
# 11.3 persons
# ---------------------------------------------------------------------------
class Person(Base):
    __tablename__ = "persons"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    primary_area_id = Column(UUID(as_uuid=True), ForeignKey("functional_areas.id", ondelete="SET NULL"), nullable=True)
    reports_to_person_id = Column(UUID(as_uuid=True), ForeignKey("persons.id", ondelete="SET NULL"), nullable=True)
    name = Column(Text, nullable=False)
    title = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    search_vector = Column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', coalesce(name,'') || ' ' || coalesce(title,''))",
            persisted=True,
        ),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_persons_company_id", "company_id"),
        Index("ix_persons_reports_to_person_id", "reports_to_person_id"),
        Index("ix_persons_search_vector", "search_vector", postgresql_using="gin"),
    )

    company = relationship("Company", back_populates="persons")
    primary_area = relationship("FunctionalArea", back_populates="persons")
    reports_to = relationship("Person", remote_side="Person.id", foreign_keys=[reports_to_person_id])
    action_items = relationship("ActionItem", back_populates="person")

    # Relationships where this person is subordinate or manager
    subordinate_relationships = relationship(
        "Relationship",
        foreign_keys="Relationship.subordinate_person_id",
        back_populates="subordinate",
    )
    manager_relationships = relationship(
        "Relationship",
        foreign_keys="Relationship.manager_person_id",
        back_populates="manager",
    )


# ---------------------------------------------------------------------------
# 11.4 sources
# ---------------------------------------------------------------------------
class Source(Base):
    __tablename__ = "sources"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    type = Column(Text, nullable=False)
    filename_or_subject = Column(Text, nullable=True)
    raw_content = Column(Text, nullable=False)
    file_path = Column(Text, nullable=True)
    received_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    who = Column(Text, nullable=True)
    interaction_date = Column(Text, nullable=True)
    src = Column(Text, nullable=True)
    status = Column(Text, nullable=False, server_default=text("'pending'"))
    error = Column(Text, nullable=True)
    raw_llm_response = Column(Text, nullable=True)
    search_vector = Column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', coalesce(filename_or_subject,'') || ' ' || coalesce(raw_content,''))",
            persisted=True,
        ),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint("type IN ('email', 'upload')", name="ck_sources_type"),
        CheckConstraint(
            "status IN ('pending', 'processing', 'processed', 'failed')",
            name="ck_sources_status",
        ),
        Index("ix_sources_company_id", "company_id"),
        Index("ix_sources_status", "status"),
        Index("ix_sources_received_at", text("received_at DESC")),
        Index("ix_sources_search_vector", "search_vector", postgresql_using="gin"),
    )

    company = relationship("Company", back_populates="sources")
    inferred_facts = relationship("InferredFact", back_populates="source", cascade="all, delete-orphan")
    action_items = relationship("ActionItem", back_populates="source")


# ---------------------------------------------------------------------------
# 11.5 inferred_facts
# ---------------------------------------------------------------------------
class InferredFact(Base):
    __tablename__ = "inferred_facts"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.id", ondelete="CASCADE"), nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    functional_area_id = Column(UUID(as_uuid=True), ForeignKey("functional_areas.id", ondelete="SET NULL"), nullable=True)
    category = Column(Text, nullable=False)
    inferred_value = Column(Text, nullable=False)
    source_line = Column(Text, nullable=True)
    corrected_value = Column(Text, nullable=True)
    status = Column(Text, nullable=False, server_default=text("'pending'"))
    merged_into_entity_type = Column(Text, nullable=True)
    merged_into_entity_id = Column(UUID(as_uuid=True), nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    search_vector = Column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', coalesce(inferred_value,'') || ' ' || coalesce(corrected_value,''))",
            persisted=True,
        ),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "category IN ("
            "'functional-area', 'person', 'relationship', "
            "'technology', 'process', "
            "'cgkra-cs', 'cgkra-gw', 'cgkra-kp', 'cgkra-rm', 'cgkra-aop', "
            "'swot-s', 'swot-w', 'swot-o', 'swot-th', "
            "'action-item', 'other'"
            ")",
            name="ck_inferred_facts_category",
        ),
        CheckConstraint(
            "status IN ('pending', 'accepted', 'corrected', 'merged', 'dismissed')",
            name="ck_inferred_facts_status",
        ),
        CheckConstraint(
            "merged_into_entity_type IS NULL OR merged_into_entity_type IN ('person', 'functional_area')",
            name="ck_inferred_facts_merged_entity_type",
        ),
        CheckConstraint(
            "status != 'merged' OR (merged_into_entity_type IS NOT NULL AND merged_into_entity_id IS NOT NULL)",
            name="ck_inferred_facts_merged_requires_target",
        ),
        CheckConstraint(
            "status != 'corrected' OR corrected_value IS NOT NULL",
            name="ck_inferred_facts_corrected_requires_value",
        ),
        Index("ix_inferred_facts_company_status", "company_id", "status"),
        Index("ix_inferred_facts_source_id", "source_id"),
        Index("ix_inferred_facts_category", "category"),
        Index("ix_inferred_facts_functional_area_id", "functional_area_id"),
        Index("ix_inferred_facts_search_vector", "search_vector", postgresql_using="gin"),
    )

    source = relationship("Source", back_populates="inferred_facts")
    company = relationship("Company", back_populates="inferred_facts")
    functional_area = relationship("FunctionalArea", back_populates="inferred_facts")
    action_items = relationship("ActionItem", back_populates="inferred_fact")


# ---------------------------------------------------------------------------
# 11.6 relationships
# ---------------------------------------------------------------------------
class Relationship(Base):
    __tablename__ = "relationships"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    subordinate_person_id = Column(UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    manager_person_id = Column(UUID(as_uuid=True), ForeignKey("persons.id", ondelete="CASCADE"), nullable=False)
    inferred_fact_id = Column(UUID(as_uuid=True), ForeignKey("inferred_facts.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("subordinate_person_id", "manager_person_id", name="uq_relationships_sub_mgr"),
        Index("ix_relationships_company_id", "company_id"),
        Index("ix_relationships_subordinate_person_id", "subordinate_person_id"),
        Index("ix_relationships_manager_person_id", "manager_person_id"),
    )

    company = relationship("Company", back_populates="relationships_list")
    subordinate = relationship("Person", foreign_keys=[subordinate_person_id], back_populates="subordinate_relationships")
    manager = relationship("Person", foreign_keys=[manager_person_id], back_populates="manager_relationships")
    inferred_fact = relationship("InferredFact")


# ---------------------------------------------------------------------------
# 11.7 action_items
# ---------------------------------------------------------------------------
class ActionItem(Base):
    __tablename__ = "action_items"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    person_id = Column(UUID(as_uuid=True), ForeignKey("persons.id", ondelete="SET NULL"), nullable=True)
    functional_area_id = Column(UUID(as_uuid=True), ForeignKey("functional_areas.id", ondelete="SET NULL"), nullable=True)
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True)
    inferred_fact_id = Column(UUID(as_uuid=True), ForeignKey("inferred_facts.id", ondelete="SET NULL"), nullable=True)
    description = Column(Text, nullable=False)
    status = Column(Text, nullable=False, server_default=text("'open'"))
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    search_vector = Column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', coalesce(description,'') || ' ' || coalesce(notes,''))",
            persisted=True,
        ),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint("status IN ('open', 'complete')", name="ck_action_items_status"),
        Index("ix_action_items_company_status", "company_id", "status"),
        Index("ix_action_items_status", "status"),
        Index("ix_action_items_search_vector", "search_vector", postgresql_using="gin"),
    )

    company = relationship("Company", back_populates="action_items")
    person = relationship("Person", back_populates="action_items")
    functional_area = relationship("FunctionalArea", back_populates="action_items")
    source = relationship("Source", back_populates="action_items")
    inferred_fact = relationship("InferredFact", back_populates="action_items")


# ---------------------------------------------------------------------------
# 11.8 cgkra_templates
# ---------------------------------------------------------------------------
class CGKRATemplate(Base):
    __tablename__ = "cgkra_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    name = Column(Text, nullable=False)
    file_path = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    generated_documents = relationship("GeneratedDocument", back_populates="template")


# ---------------------------------------------------------------------------
# 11.9 generated_documents
# ---------------------------------------------------------------------------
class GeneratedDocument(Base):
    __tablename__ = "generated_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    type = Column(Text, nullable=False)
    format = Column(Text, nullable=False)
    status = Column(Text, nullable=False, server_default=text("'pending'"))
    file_path = Column(Text, nullable=True)
    template_id = Column(UUID(as_uuid=True), ForeignKey("cgkra_templates.id", ondelete="SET NULL"), nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("type IN ('briefing', 'cgkra-narrative')", name="ck_generated_documents_type"),
        CheckConstraint("format IN ('pdf', 'docx', 'markdown')", name="ck_generated_documents_format"),
        CheckConstraint(
            "status IN ('pending', 'processing', 'ready', 'failed')",
            name="ck_generated_documents_status",
        ),
        Index("ix_generated_documents_company_type", "company_id", "type"),
        Index("ix_generated_documents_status", "status"),
    )

    company = relationship("Company", back_populates="generated_documents")
    template = relationship("CGKRATemplate", back_populates="generated_documents")


# ---------------------------------------------------------------------------
# 11.10 sessions
# ---------------------------------------------------------------------------
class Session(Base):
    __tablename__ = "sessions"

    token = Column(Text, primary_key=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    last_active_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        Index("ix_sessions_last_active_at", "last_active_at"),
    )


# ---------------------------------------------------------------------------
# 11.11 credentials
# ---------------------------------------------------------------------------
class Credential(Base):
    __tablename__ = "credentials"

    id = Column(Integer, primary_key=True, default=1, server_default=text("1"))
    username = Column(Text, nullable=False)
    password_hash = Column(Text, nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
