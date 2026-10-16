import os
from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from database import get_connection, init_db, is_mysql, get_friday_date

app = FastAPI(title="Zentegra Friday Snacks API", version="1.0.0")

# Enable CORS so your Hostinger frontend can communicate smoothly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    try:
        init_db()
        ensure_current_session()
        print("Database initialized successfully!")
    except Exception as e:
        print(f"Startup database initialization error: {e}")

def dict_row(row):
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    return dict(row)

def dict_rows(rows):
    return [dict_row(r) for r in rows]

def execute_query(query, params=(), fetchone=False, fetchall=False, commit=True):
    conn = get_connection()
    cursor = conn.cursor()
    # Replace ? with %s if MySQL
    if is_mysql():
        formatted_query = query.replace("?", "%s")
    else:
        formatted_query = query.replace("%s", "?")

    cursor.execute(formatted_query, params)
    
    data = None
    if fetchone:
        data = dict_row(cursor.fetchone())
    elif fetchall:
        data = dict_rows(cursor.fetchall())
        
    last_id = cursor.lastrowid
    
    if not is_mysql() and commit:
        conn.commit()
        
    conn.close()
    return data, last_id

def log_audit(order_id, action, performed_by, details):
    try:
        details_str = str(details)
        execute_query(
            "INSERT INTO audit_logs (order_id, action, performed_by, details) VALUES (?, ?, ?, ?)",
            (order_id, action, performed_by, details_str)
        )
    except Exception as e:
        print(f"Audit log error: {e}")

def ensure_current_session():
    friday_date = get_friday_date()
    session, _ = execute_query(
        "SELECT * FROM friday_sessions WHERE session_date = ?",
        (friday_date,),
        fetchone=True
    )
    if not session:
        _, last_id = execute_query(
            "INSERT INTO friday_sessions (session_date, allowance_amount, status, notes) VALUES (?, 100, 'open', 'Automated Friday Session')",
            (friday_date,)
        )
        session, _ = execute_query(
            "SELECT * FROM friday_sessions WHERE id = ?",
            (last_id,),
            fetchone=True
        )
    return session

# --- Public Endpoints ---

@app.get("/")
def home():
    return {
        "status": "online",
        "service": "Zentegra Friday Snacks API",
        "documentation": "/docs"
    }

@app.get("/api/settings")
def get_settings():
    rows, _ = execute_query("SELECT `key`, `value` FROM app_settings", fetchall=True)
    settings = {r["key"]: r["value"] for r in rows}
    settings.pop("admin_pin", None)
    return {"success": True, "settings": settings}

@app.get("/api/employees")
def get_employees():
    employees, _ = execute_query("SELECT id, name FROM employees ORDER BY name ASC", fetchall=True)
    return {"success": True, "employees": employees}

@app.get("/api/sessions")
def get_sessions():
    ensure_current_session()
    sessions, _ = execute_query("SELECT * FROM friday_sessions ORDER BY session_date DESC", fetchall=True)
    return {"success": True, "sessions": sessions}

@app.get("/api/orders/my-order")
def get_my_order(employee_id: int, session_id: Optional[int] = None):
    if not session_id:
        sess = ensure_current_session()
        session_id = sess["id"]

    order, _ = execute_query("""
        SELECT o.*, e.name as employee_name, s.session_date, s.status as session_status, s.allowance_amount
        FROM orders o
        JOIN employees e ON o.employee_id = e.id
        JOIN friday_sessions s ON o.session_id = s.id
        WHERE o.employee_id = ? AND o.session_id = ?
    """, (employee_id, session_id), fetchone=True)

    session, _ = execute_query("SELECT * FROM friday_sessions WHERE id = ?", (session_id,), fetchone=True)
    return {"success": True, "order": order, "session": session}

# --- Order Submission ---

class OrderCreateRequest(BaseModel):
    employee_id: int
    session_id: Optional[int] = None
    food_amount: float
    payment_mode: Optional[str] = "NONE"

@app.post("/api/orders")
def submit_order(req: OrderCreateRequest):
    if req.food_amount <= 0:
        raise HTTPException(status_code=400, detail="Valid total food amount is required")

    emp, _ = execute_query("SELECT * FROM employees WHERE id = ?", (req.employee_id,), fetchone=True)
    if not emp:
        raise HTTPException(status_code=404, detail="Employee not found")

    if req.session_id:
        session, _ = execute_query("SELECT * FROM friday_sessions WHERE id = ?", (req.session_id,), fetchone=True)
    else:
        session = ensure_current_session()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.get("status") == "closed":
        raise HTTPException(status_code=400, detail="This Friday session is closed by admin. No edits permitted.")

    allowance = float(session.get("allowance_amount") or 100.0)
    food_num = float(req.food_amount)
    company_pays = min(allowance, food_num)
    employee_pays = max(0.0, food_num - allowance)

    chosen_mode = req.payment_mode or "NONE"
    if employee_pays == 0:
        calculated_status = "Fully Covered"
        chosen_mode = "NONE"
    else:
        if chosen_mode == "CASH":
            calculated_status = "Cash Pending"
        else:
            calculated_status = "UPI Verification Pending"
            chosen_mode = "UPI"

    existing_order, _ = execute_query(
        "SELECT * FROM orders WHERE session_id = ? AND employee_id = ?",
        (session["id"], emp["id"]),
        fetchone=True
    )

    if existing_order:
        order_id = existing_order["id"]
        execute_query("""
            UPDATE orders SET
                food_amount = ?,
                company_pays = ?,
                employee_pays = ?,
                payment_mode = ?,
                payment_status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (food_num, company_pays, employee_pays, chosen_mode, calculated_status, order_id))

        log_audit(order_id, "ORDER_UPDATED", emp["name"], {
            "food": food_num,
            "status": calculated_status,
            "mode": chosen_mode
        })
    else:
        session_date_clean = str(session["session_date"]).replace("-", "")
        count_data, _ = execute_query(
            "SELECT count(*) as c FROM orders WHERE session_id = ?",
            (session["id"],),
            fetchone=True
        )
        count = count_data["c"] if count_data else 0
        order_ref = f"ZS-{session_date_clean}-{str(count + 1).zfill(3)}"

        _, order_id = execute_query("""
            INSERT INTO orders 
            (order_ref, session_id, employee_id, food_amount, company_pays, employee_pays, payment_mode, payment_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (order_ref, session["id"], emp["id"], food_num, company_pays, employee_pays, chosen_mode, calculated_status))

        log_audit(order_id, "ORDER_CREATED", emp["name"], {
            "food": food_num,
            "status": calculated_status,
            "mode": chosen_mode
        })

    saved_order, _ = execute_query("""
        SELECT o.*, e.name as employee_name, s.session_date, s.allowance_amount
        FROM orders o
        JOIN employees e ON o.employee_id = e.id
        JOIN friday_sessions s ON o.session_id = s.id
        WHERE o.id = ?
    """, (order_id,), fetchone=True)

    return {"success": True, "order": saved_order}

class PaymentConfirmRequest(BaseModel):
    payment_mode: Optional[str] = "UPI"
    upi_reference: Optional[str] = None

@app.post("/api/orders/{order_id}/confirm-payment")
def confirm_payment(order_id: int, req: PaymentConfirmRequest):
    order, _ = execute_query(
        "SELECT o.*, e.name as employee_name FROM orders o JOIN employees e ON o.employee_id = e.id WHERE o.id = ?",
        (order_id,),
        fetchone=True
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    mode = req.payment_mode or order.get("payment_mode") or "UPI"
    new_status = "Cash Pending" if mode == "CASH" else "UPI Verification Pending"

    execute_query("""
        UPDATE orders SET
            payment_mode = ?,
            payment_status = ?,
            upi_reference = COALESCE(?, upi_reference),
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (mode, new_status, req.upi_reference, order_id))

    log_audit(order_id, "PAYMENT_SUBMITTED", order["employee_name"], {"mode": mode, "status": new_status})

    updated_order, _ = execute_query("""
        SELECT o.*, e.name as employee_name, s.session_date, s.allowance_amount
        FROM orders o
        JOIN employees e ON o.employee_id = e.id
        JOIN friday_sessions s ON o.session_id = s.id
        WHERE o.id = ?
    """, (order_id,), fetchone=True)

    return {"success": True, "order": updated_order}

# --- Admin Controls ---

class AdminLoginRequest(BaseModel):
    pin: str

@app.post("/api/admin/login")
def admin_login(req: AdminLoginRequest):
    setting, _ = execute_query("SELECT value FROM app_settings WHERE `key` = 'admin_pin'", fetchone=True)
    admin_pin = setting["value"] if setting else "admin123"

    if req.pin == admin_pin:
        return {"success": True, "token": "zentegra_admin_session_auth_token_99"}
    raise HTTPException(status_code=401, detail="Incorrect Admin PIN / Password")

def verify_admin(authorization: Optional[str] = Header(None)):
    if not authorization or "zentegra_admin_session_auth_token_99" not in authorization:
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.get("/api/admin/dashboard")
def get_dashboard(session_id: Optional[int] = None, authorization: Optional[str] = Header(None)):
    verify_admin(authorization)
    ensure_current_session()

    if session_id:
        target_session, _ = execute_query("SELECT * FROM friday_sessions WHERE id = ?", (session_id,), fetchone=True)
    else:
        target_session = ensure_current_session()

    if not target_session:
        raise HTTPException(status_code=404, detail="Session not found")

    all_employees, _ = execute_query("SELECT id, name FROM employees ORDER BY name ASC", fetchall=True)
    orders, _ = execute_query("""
        SELECT o.*, e.name as employee_name
        FROM orders o
        JOIN employees e ON o.employee_id = e.id
        WHERE o.session_id = ?
    """, (target_session["id"],), fetchall=True)

    orders_by_emp = {o["employee_id"]: o for o in orders}

    submitted_count = 0
    total_food = 0.0
    total_company = 0.0
    total_excess = 0.0
    total_upi_collected = 0.0
    total_cash_collected = 0.0
    total_pending = 0.0

    employee_reports = []
    for emp in all_employees:
        o = orders_by_emp.get(emp["id"])
        if o:
            submitted_count += 1
            food = float(o["food_amount"])
            comp = float(o["company_pays"])
            emp_pay = float(o["employee_pays"])
            total_food += food
            total_company += comp
            total_excess += emp_pay

            status = o["payment_status"]
            mode = o["payment_mode"]

            if status == "Paid":
                if mode == "UPI":
                    total_upi_collected += emp_pay
                elif mode == "CASH":
                    total_cash_collected += emp_pay
            elif "Pending" in status:
                total_pending += emp_pay

            employee_reports.append({
                "employee_id": emp["id"],
                "employee_name": emp["name"],
                "order_id": o["id"],
                "order_ref": o["order_ref"],
                "food_amount": food,
                "company_pays": comp,
                "employee_pays": emp_pay,
                "payment_mode": mode,
                "payment_status": status,
                "upi_reference": o.get("upi_reference"),
                "paid_at": str(o.get("paid_at") or ""),
                "submitted_at": str(o.get("submitted_at") or "")
            })
        else:
            employee_reports.append({
                "employee_id": emp["id"],
                "employee_name": emp["name"],
                "order_id": None,
                "order_ref": None,
                "food_amount": 0.0,
                "company_pays": 0.0,
                "employee_pays": 0.0,
                "payment_mode": "NONE",
                "payment_status": "Not Submitted",
                "upi_reference": None,
                "paid_at": None,
                "submitted_at": None
            })

    vendor_expenses, _ = execute_query(
        "SELECT * FROM vendor_expenses WHERE session_id = ? ORDER BY id DESC",
        (target_session["id"],),
        fetchall=True
    )
    total_vendor_inv = sum(float(v["invoice_amount"]) for v in vendor_expenses)
    total_vendor_paid = sum(float(v["amount_paid"]) for v in vendor_expenses)
    collected = total_upi_collected + total_cash_collected
    net_expense = max(0.0, total_vendor_paid - collected)

    return {
        "success": True,
        "session": target_session,
        "summary": {
            "totalEmployees": len(all_employees),
            "employeesEntered": submitted_count,
            "employeesNotSubmitted": len(all_employees) - submitted_count,
            "totalFoodExpense": total_food,
            "companyContribution": total_company,
            "totalEmployeeExcessAmount": total_excess,
            "upiAmountCollected": total_upi_collected,
            "cashAmountCollected": total_cash_collected,
            "totalPendingCollection": total_pending
        },
        "vendorSummary": {
            "totalVendorInvoice": total_vendor_inv,
            "totalVendorPaid": total_vendor_paid,
            "employeeContributionDue": total_excess,
            "amountAlreadyCollected": collected,
            "remainingOutstanding": total_pending,
            "companyNetExpense": net_expense
        },
        "employeeReports": employee_reports,
        "vendorExpenses": vendor_expenses
    }

class VerifyOrderRequest(BaseModel):
    action_type: Optional[str] = "VERIFIED"
    notes: Optional[str] = ""

@app.post("/api/admin/orders/{order_id}/verify")
def verify_order(order_id: int, req: VerifyOrderRequest, authorization: Optional[str] = Header(None)):
    verify_admin(authorization)
    order, _ = execute_query(
        "SELECT o.*, e.name as employee_name FROM orders o JOIN employees e ON o.employee_id = e.id WHERE o.id = ?",
        (order_id,),
        fetchone=True
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    execute_query("UPDATE orders SET payment_status = 'Paid', paid_at = CURRENT_TIMESTAMP WHERE id = ?", (order_id,))
    log_audit(order_id, "PAYMENT_VERIFIED", "Admin", {"employee": order["employee_name"], "notes": req.notes})
    return {"success": True, "message": "Payment verified successfully"}

class UpdateOrderRequest(BaseModel):
    food_amount: float
    payment_mode: str
    payment_status: str
    audit_reason: str

@app.post("/api/admin/orders/{order_id}/update")
def update_order_record(order_id: int, req: UpdateOrderRequest, authorization: Optional[str] = Header(None)):
    verify_admin(authorization)
    if not req.audit_reason:
        raise HTTPException(status_code=400, detail="Audit reason is required")

    allowance = 100.0
    food = req.food_amount
    comp = min(allowance, food)
    emp_pays = max(0.0, food - allowance)

    execute_query("""
        UPDATE orders SET
            food_amount = ?,
            company_pays = ?,
            employee_pays = ?,
            payment_mode = ?,
            payment_status = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (food, comp, emp_pays, req.payment_mode, req.payment_status, order_id))

    log_audit(order_id, "ADMIN_CORRECTION", "Admin", {"reason": req.audit_reason, "new_food": food, "new_status": req.payment_status})
    return {"success": True, "message": "Record updated"}

class SessionToggleRequest(BaseModel):
    session_id: int
    status: str

@app.post("/api/admin/sessions/toggle")
def toggle_session(req: SessionToggleRequest, authorization: Optional[str] = Header(None)):
    verify_admin(authorization)
    execute_query("UPDATE friday_sessions SET status = ? WHERE id = ?", (req.status, req.session_id))
    log_audit(None, "SESSION_STATUS_CHANGED", "Admin", {"sessionId": req.session_id, "status": req.status})
    return {"success": True, "message": f"Session marked as {req.status}"}

class SettingsUpdateRequest(BaseModel):
    upi_id: Optional[str] = None
    upi_name: Optional[str] = None
    allowance_amount: Optional[str] = None
    admin_pin: Optional[str] = None

@app.post("/api/admin/settings")
def update_settings(req: SettingsUpdateRequest, authorization: Optional[str] = Header(None)):
    verify_admin(authorization)
    for key, val in [("upi_id", req.upi_id), ("upi_name", req.upi_name), ("allowance_amount", req.allowance_amount), ("admin_pin", req.admin_pin)]:
        if val:
            execute_query("INSERT INTO app_settings (`key`, `value`) VALUES (?, ?) ON DUPLICATE KEY UPDATE `value` = VALUES(`value`)", (key, val))
    return {"success": True, "message": "Settings updated"}

@app.get("/api/admin/audit-logs")
def get_audit_logs(authorization: Optional[str] = Header(None)):
    verify_admin(authorization)
    logs, _ = execute_query("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 100", fetchall=True)
    return {"success": True, "logs": logs}
