from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models.entities import Shipment, AuditLog, User, Truck, Load
from app.models.enums import ShipmentState, UserRole, TruckStatus, LoadStatus

class ShipmentStateMachine:
    """
    Strict 14-State Shipment State Machine with actor RBAC, idempotency, and audit logging (PRD Section 13).
    """

    ALLOWED_TRANSITIONS: Dict[ShipmentState, List[ShipmentState]] = {
        ShipmentState.CONFIRMED: [ShipmentState.DRIVER_EN_ROUTE, ShipmentState.CANCELLED],
        ShipmentState.DRIVER_EN_ROUTE: [ShipmentState.ARRIVED_PICKUP, ShipmentState.CANCELLED],
        ShipmentState.ARRIVED_PICKUP: [ShipmentState.LOADING, ShipmentState.CANCELLED],
        ShipmentState.LOADING: [ShipmentState.LOADED],
        ShipmentState.LOADED: [ShipmentState.IN_TRANSIT],
        ShipmentState.IN_TRANSIT: [ShipmentState.NEAR_DESTINATION, ShipmentState.DELIVERED],
        ShipmentState.NEAR_DESTINATION: [ShipmentState.DELIVERED],
        ShipmentState.DELIVERED: [ShipmentState.POD_SUBMITTED, ShipmentState.DISPUTED],
        ShipmentState.POD_SUBMITTED: [ShipmentState.COMPLETED, ShipmentState.DISPUTED],
        ShipmentState.DISPUTED: [ShipmentState.COMPLETED, ShipmentState.CANCELLED],
        ShipmentState.COMPLETED: [],
        ShipmentState.CANCELLED: [],
    }

    ACTOR_STATE_PERMISSIONS: Dict[ShipmentState, List[UserRole]] = {
        ShipmentState.DRIVER_EN_ROUTE: [UserRole.DRIVER, UserRole.ADMIN],
        ShipmentState.ARRIVED_PICKUP: [UserRole.DRIVER, UserRole.ADMIN],
        ShipmentState.LOADING: [UserRole.DRIVER, UserRole.DEALER, UserRole.ADMIN],
        ShipmentState.LOADED: [UserRole.DRIVER, UserRole.DEALER, UserRole.ADMIN],
        ShipmentState.IN_TRANSIT: [UserRole.DRIVER, UserRole.ADMIN],
        ShipmentState.NEAR_DESTINATION: [UserRole.DRIVER, UserRole.ADMIN],
        ShipmentState.DELIVERED: [UserRole.DRIVER, UserRole.ADMIN],
        ShipmentState.POD_SUBMITTED: [UserRole.DRIVER, UserRole.ADMIN],
        ShipmentState.COMPLETED: [UserRole.DEALER, UserRole.ADMIN],
        ShipmentState.CANCELLED: [UserRole.DEALER, UserRole.DRIVER, UserRole.ADMIN],
        ShipmentState.DISPUTED: [UserRole.DEALER, UserRole.DRIVER, UserRole.ADMIN],
    }

    @classmethod
    async def transition(
        cls,
        session: AsyncSession,
        shipment: Shipment,
        target_state: ShipmentState,
        actor_user: User,
        idempotency_key: Optional[str] = None,
        note: Optional[str] = None,
    ) -> Shipment:
        current_state = shipment.state

        # 1. Idempotency Check
        if current_state == target_state:
            # Already in target state, return gracefully without duplicate mutation
            return shipment

        if idempotency_key and shipment.idempotency_key == idempotency_key:
            return shipment

        # 2. Check Valid Edge in State Graph
        allowed = cls.ALLOWED_TRANSITIONS.get(current_state, [])
        if target_state not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid state transition from '{current_state.value}' to '{target_state.value}'. Allowed targets: {[s.value for s in allowed]}",
            )

        # 3. Actor Role Authorization
        allowed_roles = cls.ACTOR_STATE_PERMISSIONS.get(target_state, [UserRole.ADMIN])
        if actor_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User with role '{actor_user.role.value}' is not permitted to trigger transition to '{target_state.value}'.",
            )

        # 4. Contextual Actor Verification (e.g. Ensure driver is the assigned driver)
        if actor_user.role == UserRole.DRIVER and actor_user.driver_profile:
            if shipment.driver_id != actor_user.driver_profile.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Driver is not assigned to this shipment.",
                )
        if actor_user.role == UserRole.DEALER and actor_user.dealer_profile:
            if shipment.dealer_id != actor_user.dealer_profile.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Dealer does not own this shipment.",
                )

        # 4.5. Insurance Dispatch Gate: Prevent dispatch if required insurance is unverified
        if target_state in [ShipmentState.DRIVER_EN_ROUTE, ShipmentState.IN_TRANSIT]:
            from sqlalchemy import select, or_
            from app.models.entities import CargoInsurance
            from app.services.insurance_service import InsuranceService

            q_ins = select(CargoInsurance).where(
                or_(
                    CargoInsurance.shipment_id == shipment.id,
                    CargoInsurance.booking_id == shipment.booking_id,
                    CargoInsurance.load_id == shipment.load_id,
                )
            )
            res_ins = await session.execute(q_ins)
            ins_rec = res_ins.scalars().first()

            if ins_rec:
                permitted, reason = InsuranceService.is_dispatch_permitted(ins_rec)
                if not permitted:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Dispatch blocked by Risk-Based Insurance policy: {reason}",
                    )

        # 4.6 Concurrency & Duplicate Dispatch Protection (Master Prompt 2.1 Task 5)
        if target_state in [ShipmentState.DRIVER_EN_ROUTE, ShipmentState.IN_TRANSIT]:
            from sqlalchemy import select
            if shipment.truck:
                if shipment.truck.status == TruckStatus.SAFETY_HOLD:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Truck {shipment.truck.registration_no} is on SAFETY_HOLD and cannot be dispatched.",
                    )
                if shipment.truck.status == TruckStatus.MAINTENANCE:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Truck {shipment.truck.registration_no} is under MAINTENANCE and cannot be dispatched.",
                    )

            # Prevent duplicate active dispatch of the same truck across concurrent shipments
            q_other_active = select(Shipment).where(
                Shipment.truck_id == shipment.truck_id,
                Shipment.id != shipment.id,
                Shipment.state.in_([
                    ShipmentState.DRIVER_EN_ROUTE,
                    ShipmentState.ARRIVED_PICKUP,
                    ShipmentState.IN_TRANSIT,
                    ShipmentState.NEAR_DESTINATION
                ])
            )
            other_active = (await session.execute(q_other_active)).scalar_one_or_none()
            if other_active:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Cannot dispatch vehicle: Truck is already actively dispatched on shipment '{other_active.id}' in state '{other_active.state.value}'.",
                )

        # 5. Apply Domain Side Effects
        now = datetime.now(timezone.utc)
        shipment.state = target_state
        shipment.updated_at = now
        if idempotency_key:
            shipment.idempotency_key = idempotency_key

        if target_state == ShipmentState.ARRIVED_PICKUP and not shipment.actual_pickup_time:
            shipment.actual_pickup_time = now
        elif target_state == ShipmentState.DELIVERED and not shipment.actual_delivery_time:
            shipment.actual_delivery_time = now
            if shipment.truck:
                shipment.truck.status = TruckStatus.ONLINE_AVAILABLE
        elif target_state == ShipmentState.IN_TRANSIT:
            if shipment.truck:
                shipment.truck.status = TruckStatus.IN_TRANSIT
        elif target_state == ShipmentState.COMPLETED:
            if shipment.load:
                shipment.load.status = LoadStatus.COMPLETED
            if shipment.truck:
                shipment.truck.status = TruckStatus.ONLINE_AVAILABLE

        # 6. Record Immutable Audit Log
        audit_log = AuditLog(
            actor_id=actor_user.id,
            action=f"SHIPMENT_STATE_TRANSITION_{target_state.value}",
            entity_name="Shipment",
            entity_id=shipment.id,
            state_before=current_state.value,
            state_after=target_state.value,
            metadata_json={"note": note or "", "idempotency_key": idempotency_key or ""},
            timestamp=now,
        )
        session.add(audit_log)
        await session.flush()

        return shipment

state_machine = ShipmentStateMachine()
