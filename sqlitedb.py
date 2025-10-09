import sqlite3
from typing import Dict, Any, List
from datetime import datetime
import uuid

class GeneralDatabase:
    def __init__(self, db_file: str = "database.db"):
        self.db_file = db_file

    def _connect(self):
        return sqlite3.connect(self.db_file)

    def create_table(self, table_name: str, columns: Dict[str, str]):
        try:
            cols_def = ", ".join([f"{k} {v}" for k, v in columns.items()])
            query = f"CREATE TABLE IF NOT EXISTS {table_name} ({cols_def})"
            with self._connect() as conn:
                conn.execute(query)
                conn.commit()
        except Exception as e:
            print(f"Error creating table {table_name}:", e)

    def insert(self, table_name: str, data: Dict[str, Any]):
        try:
            columns = ", ".join(data.keys())
            placeholders = ", ".join(["?"] * len(data))
            values = tuple(data.values())
            query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
            with self._connect() as conn:
                conn.execute(query, values)
                conn.commit()
        except Exception as e:
            print(f"Error inserting into {table_name}:", e)

    def update(self, table_name: str, data: Dict[str, Any], where: str, where_params: tuple):
        try:
            with self._connect() as conn:
                cursor = conn.execute(f"SELECT 1 FROM {table_name} WHERE {where}", where_params)
                if cursor.fetchone() is None:
                    print(f"Update failed: record not found in {table_name}")
                    return False
                set_clause = ", ".join([f"{k}=?" for k in data.keys()])
                values = tuple(data.values()) + where_params
                query = f"UPDATE {table_name} SET {set_clause} WHERE {where}"
                conn.execute(query, values)
                conn.commit()
            return True
        except Exception as e:
            print(f"Error updating {table_name}:", e)
            return False

    def delete(self, table_name: str, where: str, where_params: tuple):
        try:
            with self._connect() as conn:
                cursor = conn.execute(f"SELECT 1 FROM {table_name} WHERE {where}", where_params)
                if cursor.fetchone() is None:
                    print(f"Delete failed: record not found in {table_name}")
                    return False
                query = f"DELETE FROM {table_name} WHERE {where}"
                conn.execute(query, where_params)
                conn.commit()
            return True
        except Exception as e:
            print(f"Error deleting from {table_name}:", e)
            return False

    def select(self, table_name: str, columns: List[str] = None, where: str = "", where_params: tuple = ()):
        try:
            cols = ", ".join(columns) if columns else "*"
            query = f"SELECT {cols} FROM {table_name}"
            if where:
                query += f" WHERE {where}"
            with self._connect() as conn:
                cursor = conn.execute(query, where_params)
                return cursor.fetchall()
        except Exception as e:
            print(f"Error selecting from {table_name}:", e)
            return []

    def search_by_value(self, table_name: str, column: str, value: str):
    try:
        query = f"SELECT * FROM {table_name} WHERE {column} = ?"
        with self._connect() as conn:
            cursor = conn.execute(query, (value,))
            return cursor.fetchall()
    except Exception as e:
        print(f"Error searching {table_name}:", e)
        return []



 
class SessionDB(GeneralDatabase):
    TABLE_NAME = "Sessions"

    def create_table(self):
        columns = {
            "SessionId": "TEXT PRIMARY KEY",
            "CompanyId": "TEXT NOT NULL",
            "Token": "TEXT UNIQUE NOT NULL",
            "LoginTime": "TEXT NOT NULL",
            "Status": "TEXT NOT NULL",
            "TotalOrders": "INTEGER DEFAULT 0",
            "UsedOrders": "INTEGER DEFAULT 0"
        }
        super().create_table(self.TABLE_NAME, columns)

    def add_session(self, company_id: str,token:str, status: str = "Active", total_orders: int = 0, used_orders: int = 0):
        session_id = str(uuid.uuid4())
        token =token
        login_time = datetime.now().isoformat()
        super().insert(self.TABLE_NAME, {
            "SessionId": session_id,
            "CompanyId": company_id,
            "Token": token,
            "LoginTime": login_time,
            "Status": status,
            "TotalOrders": total_orders,
            "UsedOrders": used_orders
        })
        return session_id

    def increment_used_orders(self, session_id: str) -> bool:
        """
        زيادة UsedOrders بمقدار 1 بعد التحقق من TotalOrders
        """
        try:
            # جلب إجمالي الطلبات والطلبات المستخدمة الحالية
            result = super().select(self.TABLE_NAME, ["TotalOrders", "UsedOrders"], "SessionId=?", (session_id,))
            if not result:
                print("Session not found")
                return False

            total_orders, used_orders = result[0]
            if used_orders + 1 > total_orders:
                print(f"Cannot increment UsedOrders. Would exceed TotalOrders ({total_orders})")
                return False

            # تحديث القيمة بزيادة 1
            return super().update(
                self.TABLE_NAME,
                {"UsedOrders": used_orders + 1},
                "SessionId=?",
                (session_id,)
            )
        except Exception as e:
            print("Error incrementing UsedOrders:", e)
            return False

    def update_used_orders(self, session_id: str, new_used_orders: int) -> bool:
        # جلب إجمالي الطلبات
        result = super().select(self.TABLE_NAME, ["TotalOrders"], "SessionId=?", (session_id,))
        if not result:
            print("Session not found")
            return False
        total_orders = result[0][0]
        if new_used_orders > total_orders:
            print(f"Cannot update UsedOrders to {new_used_orders}. Exceeds TotalOrders ({total_orders})")
            return False
        return super().update(self.TABLE_NAME, {"UsedOrders": new_used_orders}, "SessionId=?", (session_id,))

    def check_orders(self, session_id: str) -> bool:
        result = super().select(self.TABLE_NAME, ["TotalOrders", "UsedOrders"], "SessionId=?", (session_id,))
        if not result:
            print("Session not found")
            return False
        total_orders, used_orders = result[0]
        return used_orders <= total_orders

    def search_session(self, column: str, keyword: str):
        return super().search_like(self.TABLE_NAME, column, keyword)

class CompanyDB(GeneralDatabase):
    TABLE_NAME = "Company"

    def create_table(self):
        columns = {
            "Id": "TEXT PRIMARY KEY",
            "Name": "TEXT NOT NULL",
            "LicenseNumber": "TEXT UNIQUE NOT NULL",
            "EmployeesCount": "INTEGER",
            "Services": "TEXT",
            "CreatedAt": "TEXT NOT NULL"
        }
        super().create_table(self.TABLE_NAME, columns)

    # ==========================
    # إضافة شركة
    # ==========================
    def add_company(self, name: str, license_number: str, employees: int, services: str) -> str:
        company_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        super().insert(self.TABLE_NAME, {
            "Id": company_id,
            "Name": name,
            "LicenseNumber": license_number,
            "EmployeesCount": employees,
            "Services": services,
            "CreatedAt": created_at
        })
        return company_id

    # ==========================
    # تحديث شركة
    # ==========================
    def update_company(self, company_id: str, data: Dict[str, Any]) -> bool:
        return super().update(self.TABLE_NAME, data, "Id=?", (company_id,))

    # ==========================
    # حذف شركة
    # ==========================
    def delete_company(self, company_id: str) -> bool:
        return super().delete(self.TABLE_NAME, "Id=?", (company_id,))

     
    def search_company(self, column: str, keyword: str):
        return super().search_like(self.TABLE_NAME, column, keyword)   


