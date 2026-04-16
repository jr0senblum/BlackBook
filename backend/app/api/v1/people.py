"""Route handlers for /companies/{company_id}/people/* endpoints (§10.5)."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import IntegrityError

from app.dependencies import get_current_session, get_person_service
from app.exceptions import PersonCompanyMismatchError, PersonNotFoundError
from app.repositories.functional_area_repository import FunctionalAreaRepository
from app.schemas.person import (
    ActionItemSummary,
    LinkedFactSummary,
    PersonCreatedResponse,
    PersonDetail,
    PersonListItem,
    PersonListResponse,
    PersonCreateInput,
    PersonUpdateInput,
)
from app.services.person_service import PersonService

router = APIRouter(
    prefix="/companies/{company_id}/people",
    tags=["people"],
)


def _build_detail(detail_dict: dict) -> PersonDetail:
    """Convert the service's raw dict to a PersonDetail schema.

    Handles conversion of ORM ActionItem and InferredFact objects to their
    summary schemas, computing LinkedFactSummary.value as the effective value
    (corrected_value if set, else inferred_value).
    """
    action_items = [
        ActionItemSummary(
            item_id=ai.id,
            description=ai.description,
            status=ai.status,
            notes=ai.notes,
            created_at=ai.created_at,
        )
        for ai in detail_dict["action_items"]
    ]
    inferred_facts = [
        LinkedFactSummary(
            fact_id=f.id,
            category=f.category,
            value=f.corrected_value if f.corrected_value else f.inferred_value,
            source_id=f.source_id,
        )
        for f in detail_dict["inferred_facts"]
    ]
    return PersonDetail(
        person_id=detail_dict["person_id"],
        name=detail_dict["name"],
        title=detail_dict["title"],
        primary_area_id=detail_dict["primary_area_id"],
        primary_area_name=detail_dict["primary_area_name"],
        reports_to_person_id=detail_dict["reports_to_person_id"],
        reports_to_name=detail_dict["reports_to_name"],
        action_items=action_items,
        inferred_facts=inferred_facts,
    )


@router.get("", response_model=PersonListResponse)
async def list_people(
    company_id: UUID,
    person_service: PersonService = Depends(get_person_service),
    _session: str = Depends(get_current_session),
) -> PersonListResponse:
    """List all people for a company."""
    persons = await person_service.list_people(company_id)

    # Build area name map for the company to annotate each person without
    # N+1 queries.  We reach through the person_service's functional_area_repo
    # which is already constructed for this request.
    area_repo: FunctionalAreaRepository = person_service._functional_area_repo
    areas = await area_repo.list_by_company(company_id)
    area_name_map: dict[UUID, str] = {a.id: a.name for a in areas}

    items = [
        PersonListItem(
            person_id=p.id,
            name=p.name,
            title=p.title,
            primary_area_id=p.primary_area_id,
            primary_area_name=(
                area_name_map.get(p.primary_area_id)
                if p.primary_area_id is not None
                else None
            ),
        )
        for p in persons
    ]
    return PersonListResponse(items=items)


@router.post("", response_model=PersonCreatedResponse, status_code=201)
async def create_person(
    company_id: UUID,
    body: PersonCreateInput,
    person_service: PersonService = Depends(get_person_service),
    _session: str = Depends(get_current_session),
) -> PersonCreatedResponse:
    """Create a new person for a company."""
    try:
        person = await person_service.create_person(
            company_id,
            name=body.name,
            title=body.title,
            primary_area_id=body.primary_area_id,
            reports_to_person_id=body.reports_to_person_id,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": {
                    "code": "invalid_fk",
                    "message": (
                        "primary_area_id or reports_to_person_id references "
                        "a non-existent entity"
                    ),
                }
            },
        ) from exc
    return PersonCreatedResponse(person_id=person.id, name=person.name)


@router.get("/{person_id}", response_model=PersonDetail)
async def get_person(
    company_id: UUID,
    person_id: UUID,
    person_service: PersonService = Depends(get_person_service),
    _session: str = Depends(get_current_session),
) -> PersonDetail:
    """Get enriched person detail."""
    detail = await person_service.get_person(company_id, person_id)
    return _build_detail(detail)


@router.put("/{person_id}", response_model=PersonDetail)
async def update_person(
    company_id: UUID,
    person_id: UUID,
    body: PersonUpdateInput,
    person_service: PersonService = Depends(get_person_service),
    _session: str = Depends(get_current_session),
) -> PersonDetail:
    """Update person fields.  Returns the full updated PersonDetail."""
    # Only forward fields the client explicitly included in the JSON body.
    fields = body.model_dump(include=body.model_fields_set)
    await person_service.update_person(company_id, person_id, **fields)
    # Re-fetch enriched detail after update
    detail = await person_service.get_person(company_id, person_id)
    return _build_detail(detail)


@router.delete("/{person_id}", status_code=204)
async def delete_person(
    company_id: UUID,
    person_id: UUID,
    person_service: PersonService = Depends(get_person_service),
    _session: str = Depends(get_current_session),
) -> None:
    """Delete a person."""
    await person_service.delete_person(company_id, person_id)
