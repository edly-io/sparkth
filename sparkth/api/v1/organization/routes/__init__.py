"""Org API router: the mounted unit sub-router (units at ``/org/units``)."""

from fastapi import APIRouter

from sparkth.api.v1.organization.routes import units

router = APIRouter()
router.include_router(units.router, prefix="/units")
