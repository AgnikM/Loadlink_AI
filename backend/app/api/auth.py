from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload, joinedload

from app.core.database import get_db
from app.core.security import (
    verify_password, get_password_hash, create_access_token, decode_token, oauth2_scheme, oauth2_scheme_optional
)
from app.models.entities import User, Organization, Dealer, Driver, Transporter, Truck, VehicleAssignment
from app.models.enums import UserRole, VerificationStatus, TruckStatus, FleetOwnershipType
from app.schemas.all_schemas import Token, LoginRequest, UserCreate, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    payload = decode_token(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
    query = (
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.dealer_profile).selectinload(Dealer.organization),
            selectinload(User.driver_profile).selectinload(Driver.trucks),
            selectinload(User.driver_profile).selectinload(Driver.organization),
            selectinload(User.transporter_profile).selectinload(Transporter.organization),
        )
    )
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if user.verification_status == VerificationStatus.SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is suspended. Please contact operations.",
        )
    return user

def require_roles(*allowed_roles: UserRole):
    """
    Secure backend authorization dependency enforcing RBAC across endpoints.
    A frontend role check alone is never sufficient.
    """
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. User role '{current_user.role.value}' does not have required permissions ({[r.value for r in allowed_roles]}).",
            )
        return current_user
    return role_checker

async def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: AsyncSession = Depends(get_db)
) -> Optional[User]:
    if not token:
        return None
    try:
        return await get_current_user(token, db)
    except Exception:
        return None

@router.post("/register", response_model=UserOut)
async def register(req: UserCreate, db: AsyncSession = Depends(get_db)):
    # Check duplicate email/phone
    res = await db.execute(select(User).where((User.email == req.email) | (User.phone == req.phone)))
    if res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email or phone already exists.",
        )

    user = User(
        email=req.email,
        phone=req.phone,
        password_hash=get_password_hash(req.password),
        name=req.name,
        role=req.role,
        verification_status=VerificationStatus.VERIFIED, # Pre-verify for smooth demo/pilot
    )
    db.add(user)
    await db.flush()

    if req.role == UserRole.DEALER:
        org = Organization(
            name=req.organization_name or f"{req.name}'s Freight Co",
            business_type="Manufacturing / Trading",
            org_type="DEALER_SHIPPER",
            gstin=req.gstin or "19AAACH7409R1ZZ",
            operating_corridor="Kolkata ↔ Durgapur ↔ Asansol",
            verification_status=VerificationStatus.VERIFIED,
        )
        db.add(org)
        await db.flush()

        dealer = Dealer(
            user_id=user.id,
            organization_id=org.id,
            trust_score=95.0,
        )
        db.add(dealer)

    elif req.role == UserRole.TRANSPORTER:
        org = Organization(
            name=req.organization_name or f"{req.name}'s Logistics Logistics Ltd",
            business_type="Commercial Freight Transportation",
            org_type="EXTERNAL_TRANSPORTER",
            gstin=req.gstin or "19AAACH7409R1ZT",
            operating_corridor="Kolkata ↔ Durgapur ↔ Asansol",
            verification_status=VerificationStatus.VERIFIED,
        )
        db.add(org)
        await db.flush()

        transporter = Transporter(
            user_id=user.id,
            organization_id=org.id,
            fleet_size=req.fleet_size or 5,
            trust_score=94.0,
        )
        db.add(transporter)

        if req.truck_registration_no:
            truck = Truck(
                organization_id=org.id,
                ownership_type=FleetOwnershipType.EXTERNAL_TRANSPORTER,
                registration_no=req.truck_registration_no,
                truck_type=req.truck_type or TruckType.OPEN_BODY,
                capacity_tons=req.truck_capacity_tons or 16.0,
                status=TruckStatus.ONLINE_AVAILABLE,
                verification_status=VerificationStatus.VERIFIED,
                current_lat=22.5448,
                current_lon=88.3186,
                current_location_name=req.initial_location_hub or "Kolkata Port / Docks",
            )
            db.add(truck)

    elif req.role == UserRole.FLEET_MANAGER:
        org = Organization(
            name=req.organization_name or "LoadLink Owned Fleet Operations",
            business_type="Direct Dedicated Fleet",
            org_type="LOADLINK_FLEET",
            gstin=req.gstin or "19AAACL0001L1ZZ",
            operating_corridor="Kolkata ↔ Durgapur ↔ Asansol",
            verification_status=VerificationStatus.VERIFIED,
        )
        db.add(org)
        await db.flush()

        transporter = Transporter(
            user_id=user.id,
            organization_id=org.id,
            fleet_size=req.fleet_size or 20,
            trust_score=98.0,
        )
        db.add(transporter)

        if req.truck_registration_no:
            truck = Truck(
                organization_id=org.id,
                ownership_type=FleetOwnershipType.LOADLINK_OWNED,
                registration_no=req.truck_registration_no,
                truck_type=req.truck_type or TruckType.OPEN_BODY,
                capacity_tons=req.truck_capacity_tons or 16.0,
                status=TruckStatus.ONLINE_AVAILABLE,
                verification_status=VerificationStatus.VERIFIED,
                current_lat=22.5448,
                current_lon=88.3186,
                current_location_name=req.initial_location_hub or "Kolkata Port / Docks",
            )
            db.add(truck)

    elif req.role == UserRole.DRIVER:
        driver = Driver(
            user_id=user.id,
            license_number=req.license_number or f"WB-{user.id[:8].upper()}",
            verification_status=VerificationStatus.VERIFIED,
            reliability_score=94.0,
        )
        db.add(driver)
        await db.flush()

        # Add initial truck & assignment
        truck = Truck(
            driver_id=driver.id,
            ownership_type=req.ownership_type or FleetOwnershipType.EXTERNAL_TRANSPORTER,
            registration_no=req.truck_registration_no or f"WB-39-T-{user.id[:4].upper()}",
            truck_type=req.truck_type or TruckType.OPEN_BODY,
            capacity_tons=req.truck_capacity_tons or 16.0,
            status=TruckStatus.ONLINE_AVAILABLE,
            verification_status=VerificationStatus.VERIFIED,
            current_lat=22.5448,
            current_lon=88.3186,
            current_location_name=req.initial_location_hub or "Kolkata Port / Docks",
        )
        db.add(truck)
        await db.flush()

        assignment = VehicleAssignment(
            truck_id=truck.id,
            driver_id=driver.id,
            assigned_by_user_id=user.id,
            is_active=True,
            assignment_notes="Initial driver registration assignment",
        )
        db.add(assignment)

    await db.commit()

    # Re-query user with all profiles loaded
    q_re = (
        select(User)
        .where(User.id == user.id)
        .options(
            selectinload(User.dealer_profile).selectinload(Dealer.organization),
            selectinload(User.driver_profile).selectinload(Driver.trucks),
            selectinload(User.driver_profile).selectinload(Driver.organization),
            selectinload(User.transporter_profile).selectinload(Transporter.organization),
        )
    )
    user_loaded = (await db.execute(q_re)).scalar_one()

    return _build_user_out(user_loaded)

def _build_user_out(user: User) -> UserOut:
    dealer_id = user.dealer_profile.id if user.dealer_profile else None
    driver_id = user.driver_profile.id if user.driver_profile else None
    transporter_id = user.transporter_profile.id if user.transporter_profile else None
    
    org_id = None
    org_name = None
    if user.dealer_profile and user.dealer_profile.organization:
        org_id = user.dealer_profile.organization_id
        org_name = user.dealer_profile.organization.name
    elif user.transporter_profile and user.transporter_profile.organization:
        org_id = user.transporter_profile.organization_id
        org_name = user.transporter_profile.organization.name
    elif user.driver_profile and user.driver_profile.organization:
        org_id = user.driver_profile.organization_id
        org_name = user.driver_profile.organization.name

    truck_id = None
    if user.driver_profile and user.driver_profile.trucks:
        truck_id = user.driver_profile.trucks[0].id

    score = None
    if user.dealer_profile:
        score = user.dealer_profile.trust_score
    elif user.driver_profile:
        score = user.driver_profile.reliability_score
    elif user.transporter_profile:
        score = user.transporter_profile.trust_score

    return UserOut(
        id=user.id,
        email=user.email,
        phone=user.phone,
        name=user.name,
        role=user.role,
        verification_status=user.verification_status,
        created_at=user.created_at,
        dealer_id=dealer_id,
        driver_id=driver_id,
        transporter_id=transporter_id,
        organization_id=org_id,
        organization_name=org_name,
        truck_id=truck_id,
        trust_or_reliability_score=score,
    )

@router.post("/login", response_model=Token)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    query = (
        select(User)
        .where(User.email == req.email)
        .options(
            selectinload(User.dealer_profile),
            selectinload(User.driver_profile),
            selectinload(User.transporter_profile),
        )
    )
    res = await db.execute(query)
    user = res.scalar_one_or_none()

    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    if user.verification_status == VerificationStatus.SUSPENDED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is suspended. Please contact operations.",
        )

    access_token = create_access_token(subject=user.id, role=user.role.value)
    return Token(
        access_token=access_token,
        token_type="bearer",
        role=user.role.value,
        user_id=user.id,
        name=user.name,
    )

@router.get("/me", response_model=UserOut)
async def get_me(current_user: User = Depends(get_current_user)):
    return _build_user_out(current_user)
