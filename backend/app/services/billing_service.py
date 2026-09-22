import json
import secrets
from datetime import datetime, timedelta

import requests
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.subscription import BillingPayment, Plan, Subscription


TRIAL = "TRIAL"
PRO = "PRO_MONTHLY"
PRO_ANNUAL = "PRO_ANNUAL"
ACTIVE_STATUSES = {"TRIALING", "ACTIVE", "PAST_DUE", "CANCEL_AT_PERIOD_END"}


class BillingService:
    @staticmethod
    def seed_plans(db: Session):
        definitions = [
            (TRIAL, "Free trial", 0, "trial", 30, None),
            (PRO, "Recon Pro Monthly", 20_000_000, "monthly", None, settings.PAYSTACK_PRO_PLAN_CODE),
            (PRO_ANNUAL, "Recon Pro Annual", 216_000_000, "annual", None, settings.PAYSTACK_PRO_ANNUAL_PLAN_CODE),
        ]
        for code, name, amount, interval, trial_days, gateway_code in definitions:
            plan = db.query(Plan).filter(Plan.code == code).first()
            if not plan:
                plan = Plan(code=code, name=name, amount_kobo=amount, interval=interval, trial_days=trial_days, gateway_plan_code=gateway_code)
                db.add(plan)
            else:
                # Keep catalogue pricing current for existing installations too.
                plan.name = name
                plan.amount_kobo = amount
                plan.interval = interval
                plan.trial_days = trial_days
                plan.gateway_plan_code = gateway_code
        db.flush()

    @staticmethod
    def ensure_trial(db: Session, company_id):
        BillingService.seed_plans(db)
        subscription = db.query(Subscription).filter(Subscription.company_id == company_id).order_by(Subscription.created_at.desc()).first()
        if subscription:
            return subscription
        trial = db.query(Plan).filter(Plan.code == TRIAL).one()
        now = datetime.utcnow()
        subscription = Subscription(company_id=company_id, plan_id=trial.id, status="TRIALING", trial_started_at=now, trial_ends_at=now + timedelta(days=trial.trial_days or 30))
        db.add(subscription)
        db.flush()
        return subscription

    @staticmethod
    def entitlement(db: Session, company_id):
        subscription = BillingService.ensure_trial(db, company_id)
        now = datetime.utcnow()
        if subscription.status == "TRIALING" and subscription.trial_ends_at and now >= subscription.trial_ends_at:
            subscription.status = "EXPIRED"
            subscription.ended_at = now
        elif subscription.status == "PAST_DUE" and subscription.grace_ends_at and now >= subscription.grace_ends_at:
            subscription.status = "EXPIRED"
            subscription.ended_at = now
        elif subscription.status == "CANCEL_AT_PERIOD_END" and subscription.current_period_ends_at and now >= subscription.current_period_ends_at:
            subscription.status = "CANCELLED"
            subscription.ended_at = now
        db.commit()
        db.refresh(subscription)
        plan = db.query(Plan).filter(Plan.id == subscription.plan_id).one()
        access = subscription.status in ACTIVE_STATUSES
        if subscription.status == "TRIALING" and subscription.trial_ends_at and now >= subscription.trial_ends_at:
            access = False
        return subscription, plan, access

    @staticmethod
    def serialize_entitlement(db: Session, company_id):
        subscription, plan, access = BillingService.entitlement(db, company_id)
        return {
            "plan": plan.code,
            "plan_name": plan.name,
            "status": subscription.status,
            "access": "full" if access else "billing_only",
            "trial_ends_at": subscription.trial_ends_at,
            "current_period_ends_at": subscription.current_period_ends_at,
            "grace_ends_at": subscription.grace_ends_at,
            "amount_kobo": plan.amount_kobo,
            "currency": plan.currency,
            "can_manage_billing": True,
        }

    @staticmethod
    def begin_checkout(db: Session, company, email: str, plan_code: str = PRO):
        if not settings.PAYSTACK_SECRET_KEY:
            raise ValueError("Payments are not configured. Set PAYSTACK_SECRET_KEY before enabling checkout.")
        BillingService.seed_plans(db)
        if plan_code not in {PRO, PRO_ANNUAL}:
            raise ValueError("Choose either the monthly or annual Pro plan.")
        plan = db.query(Plan).filter(Plan.code == plan_code, Plan.is_active.is_(True)).one_or_none()
        if not plan:
            raise ValueError("The selected subscription plan is unavailable.")
        if not plan.gateway_plan_code:
            raise ValueError("Payments are not configured for this plan. Add its Paystack plan code before enabling checkout.")
        subscription = BillingService.ensure_trial(db, company.id)
        reference = f"rf_{company.id.hex[:12]}_{secrets.token_urlsafe(10)}"
        payment = BillingPayment(company_id=company.id, subscription_id=subscription.id, plan_id=plan.id, provider="paystack", provider_reference=reference, amount_kobo=plan.amount_kobo, currency="NGN")
        db.add(payment)
        db.commit()
        payload = {
            "email": email,
            "amount": plan.amount_kobo,
            "currency": "NGN",
            "reference": reference,
            "callback_url": f"{settings.FRONTEND_URL.rstrip('/')}/subscription?reference={reference}",
            "metadata": {"company_id": str(company.id), "subscription_id": str(subscription.id), "plan": plan.code},
        }
        if plan.gateway_plan_code:
            payload["plan"] = plan.gateway_plan_code
        response = requests.post("https://api.paystack.co/transaction/initialize", headers={"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}, json=payload, timeout=20)
        if not response.ok:
            payment.status = "FAILED"
            payment.failure_reason = response.text[:1000]
            db.commit()
            raise ValueError("Unable to initialize payment. Please try again.")
        data = response.json().get("data", {})
        payment.provider_payload = json.dumps(data)
        db.commit()
        return {"reference": reference, "authorization_url": data.get("authorization_url")}

    @staticmethod
    def apply_success(db: Session, payment: BillingPayment, payload: dict):
        if payment.status == "SUCCESS":
            return payment
        now = datetime.utcnow()
        subscription = db.query(Subscription).filter(Subscription.id == payment.subscription_id).one()
        plan = db.query(Plan).filter(Plan.id == payment.plan_id).one_or_none()
        if not plan:
            plan_code = payload.get("metadata", {}).get("plan", PRO)
            plan = db.query(Plan).filter(Plan.code == plan_code).one()
        subscription.plan_id = plan.id
        subscription.provider = "paystack"
        provider_subscription = payload.get("subscription") or {}
        subscription.provider_customer_code = payload.get("customer", {}).get("customer_code") or subscription.provider_customer_code
        subscription.provider_subscription_code = provider_subscription.get("subscription_code") or payload.get("subscription_code") or subscription.provider_subscription_code
        subscription.provider_subscription_token = provider_subscription.get("email_token") or payload.get("email_token") or subscription.provider_subscription_token
        subscription.status = "ACTIVE"
        subscription.grace_ends_at = None
        subscription.current_period_started_at = now
        subscription.current_period_ends_at = now + timedelta(days=365 if plan.interval == "annual" else 30)
        subscription.cancel_at_period_end = False
        payment.status = "SUCCESS"
        payment.provider_transaction_id = str(payload.get("id") or "")
        payment.payment_channel = payload.get("channel")
        payment.paid_at = now
        payment.provider_payload = json.dumps(payload)
        db.commit()
        return payment

    @staticmethod
    def verify_reference(db: Session, company_id, reference: str):
        payment = db.query(BillingPayment).filter(BillingPayment.company_id == company_id, BillingPayment.provider_reference == reference).first()
        if not payment:
            raise ValueError("Payment reference not found.")
        if payment.status == "SUCCESS":
            return payment
        if not settings.PAYSTACK_SECRET_KEY:
            raise ValueError("Payments are not configured.")
        response = requests.get(f"https://api.paystack.co/transaction/verify/{reference}", headers={"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"}, timeout=20)
        if not response.ok:
            raise ValueError("Payment verification failed.")
        data = response.json().get("data", {})
        if data.get("status") == "success":
            return BillingService.apply_success(db, payment, data)
        return payment

    @staticmethod
    def record_failure(db: Session, subscription_code: str | None):
        if not subscription_code:
            return
        subscription = db.query(Subscription).filter(Subscription.provider_subscription_code == subscription_code).first()
        if subscription and subscription.status in {"ACTIVE", "CANCEL_AT_PERIOD_END"}:
            subscription.status = "PAST_DUE"
            subscription.grace_ends_at = datetime.utcnow() + timedelta(days=settings.SUBSCRIPTION_GRACE_DAYS)
            db.commit()

    @staticmethod
    def cancel_provider_subscription(subscription: Subscription):
        if subscription.provider != "paystack" or not subscription.provider_subscription_code:
            return
        if not settings.PAYSTACK_SECRET_KEY or not subscription.provider_subscription_token:
            raise ValueError("This subscription cannot be cancelled automatically yet. Please contact support.")
        response = requests.post(
            "https://api.paystack.co/subscription/disable",
            headers={"Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}"},
            json={"code": subscription.provider_subscription_code, "token": subscription.provider_subscription_token},
            timeout=20,
        )
        if not response.ok:
            raise ValueError("Paystack could not cancel this subscription. Please try again.")
