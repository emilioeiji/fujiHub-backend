from django.db import models

class Gender(models.Model):
    code = models.CharField(max_length=10, unique=True)   # Ex: M, F
    label_pt = models.CharField(max_length=50)
    label_jp = models.CharField(max_length=50)

    def __str__(self):
        return self.code


class Shift(models.Model):
    code = models.CharField(max_length=20, unique=True)   # Ex: D, N
    label_pt = models.CharField(max_length=50)
    label_jp = models.CharField(max_length=50)

    def __str__(self):
        return self.code


class Nationality(models.Model):
    code = models.CharField(max_length=10, unique=True)   # Ex: JP, BR
    name_pt = models.CharField(max_length=100)
    name_jp = models.CharField(max_length=100)

    def __str__(self):
        return self.code
    
class BillingRate(models.Model):
    code = models.CharField(max_length=10, unique=True)
    label_pt = models.CharField(max_length=50)
    label_jp = models.CharField(max_length=50)

    def __str__(self):
        return self.code
    
class Rejoined(models.Model):
    code = models.CharField(max_length=2, unique=True)
    label_pt = models.CharField(max_length=50)
    label_jp = models.CharField(max_length=50)

    def __str__(self):
        return self.code
    
class Process(models.Model):
    code = models.CharField(max_length=10, unique=True)
    label_pt = models.CharField(max_length=50)
    label_jp = models.CharField(max_length=50)

    def __str__(self):
        return self.label_jp
    
class BuildingFloor(models.Model):
    code = models.CharField(max_length=10, unique=True)
    label_pt = models.CharField(max_length=50)
    label_jp = models.CharField(max_length=50)

    def __str__(self):
        return self.code
    
class Department(models.Model):
    code = models.CharField(max_length=10, unique=True)
    label_pt = models.CharField(max_length=50)
    label_jp = models.CharField(max_length=50)

    def __str__(self):
        return self.code
    
class EntryType(models.Model):
    code = models.CharField(max_length=10, unique=True)
    label_pt = models.CharField(max_length=50)
    label_jp = models.CharField(max_length=50)

    def __str__(self):
        return self.label_jp
    
class HireType(models.Model):
    code = models.CharField(max_length=10, unique=True)
    label_pt = models.CharField(max_length=50)
    label_jp = models.CharField(max_length=50)

    def __str__(self):
        return self.label_jp

class Employee(models.Model):
    employee_id = models.CharField(max_length=20, primary_key=True)  # 社員番号
    name_jp = models.CharField(max_length=100)                       # 和名
    name_en = models.CharField(max_length=100)                       # アルファベット名
    joined_imc = models.DateField(null=True, blank=True)             # IMC入社日
    end_work = models.DateField(null=True, blank=True)               # 就労終了日
    retired = models.DateField(null=True, blank=True)                # 退職日
    notes = models.TextField(blank=True)                             # 備考
    gender_code = models.CharField(max_length=10, blank=True)        # 性別区分
    gender = models.ForeignKey("master.Gender", on_delete=models.SET_NULL, null=True, blank=True)             # 性別
    shift = models.ForeignKey("master.Shift", on_delete=models.SET_NULL, null=True, blank=True)              # シフト
    workplace_cd = models.CharField(max_length=20, blank=True)       # 統合職場CD
    workplace_name = models.CharField(max_length=100, blank=True)    # 統合職場名
    rank = models.CharField(max_length=10, blank=True)               # 単価ランク
    site_cd = models.CharField(max_length=20, blank=True)            # 職場コード
    site_abbr = models.CharField(max_length=50, blank=True)          # 職場略名
    nationality = models.ForeignKey("master.Nationality", on_delete=models.SET_NULL, null=True, blank=True)        # 国籍
    hourly_rate = models.IntegerField(null=True, blank=True)         # 時給
    new_joined = models.DateField(null=True, blank=True)             # 新異入社日
    months_worked = models.IntegerField(null=True, blank=True)       # 勤続月数
    billing_rate = models.ForeignKey("master.BillingRate", on_delete=models.SET_NULL, null=True, blank=True)       # 請求単価
    rejoined = models.ForeignKey("master.Rejoined", on_delete=models.SET_NULL, null=True, blank=True)                    # 再入
    joined_fa = models.DateField(null=True, blank=True)              # FA入社日
    birth_date = models.DateField(null=True, blank=True)             # 生年月日
    age = models.IntegerField(null=True, blank=True)                 # 年齢
    internal_name = models.CharField(max_length=100, blank=True)     # 社内名
    name_kana = models.CharField(max_length=100, blank=True)         # カナ名
    process = models.ForeignKey("master.Process", on_delete=models.SET_NULL, null=True, blank=True)            # 工程
    name_cd = models.CharField(max_length=50, blank=True)            # 氏名CD(村田用)
    active_end_month = models.BooleanField(default=False)            # 月末在職
    building_floor = models.ForeignKey("master.BuildingFloor", on_delete=models.SET_NULL, null=True, blank=True)     # 勤務棟-階
    years_elapsed = models.IntegerField(null=True, blank=True)       # 経過年
    months_elapsed = models.IntegerField(null=True, blank=True)      # 経過月
    contract_type = models.CharField(max_length=20, blank=True)      # 契約区分
    manager_flag = models.BooleanField(default=False)                 # 管理者区分
    department = models.ForeignKey("master.Department", on_delete=models.SET_NULL, null=True, blank=True)        # 所属
    ordia_number = models.CharField(max_length=50, blank=True)       # ORDIA番号
    dispatch_start = models.DateField(null=True, blank=True)         # 派遣就業開始日
    employee_cd = models.CharField(max_length=20, blank=True)        # 社員CD
    office_cd = models.CharField(max_length=20, blank=True)          # 事業所CD
    total_hourly = models.IntegerField(null=True, blank=True)        # 総時給
    elapsed_str = models.CharField(max_length=20, blank=True)        # 経過年月
    entry_type = models.ForeignKey("master.EntryType", on_delete=models.SET_NULL, null=True, blank=True)         # 入社区分
    view_flag = models.BooleanField(default=False)                   # 閲覧
    hire_type = models.ForeignKey("master.HireType", on_delete=models.SET_NULL, null=True, blank=True)          # 採用区分
    ic_card = models.CharField(max_length=50, blank=True)            # ICカード
    imc_card = models.CharField(max_length=50, blank=True)           # IMCカード

    def __str__(self):
        return f"{self.employee_id} - {self.name_en}"

class EmployeeHousing(models.Model):
    employee = models.ForeignKey(
        "master.Employee",
        on_delete=models.CASCADE,
        related_name="housing_records"
    )

    # Dados do imóvel
    property_cd = models.CharField(max_length=50, blank=True)       # 物件CD
    apartment_name = models.CharField(max_length=100, blank=True)   # アパート名
    room_number = models.CharField(max_length=20, blank=True)       # 号室

    # Custos
    r = models.IntegerField(null=True, blank=True)                  # R
    p = models.IntegerField(null=True, blank=True)                  # P
    utilities = models.IntegerField(null=True, blank=True)          # 光熱費
    dgs = models.IntegerField(null=True, blank=True)                # DGS
    monthly_payment = models.IntegerField(null=True, blank=True)    # 月額振込額
    management_fee = models.IntegerField(null=True, blank=True)     # 管理費
    fixed_fee = models.IntegerField(null=True, blank=True)          # 定額（備品）
    parking_fee = models.IntegerField(null=True, blank=True)        # 駐車場
    lga = models.IntegerField(null=True, blank=True)                # LGA
    rent = models.IntegerField(null=True, blank=True)               # 家賃
    collection_amount = models.IntegerField(null=True, blank=True)  # 回収額

    # Datas
    move_in_date = models.DateField(null=True, blank=True)          # 入寮日
    move_out_date = models.DateField(null=True, blank=True)         # 退寮日

    # Contato / endereço
    phone_number = models.CharField(max_length=20, blank=True)      # 電話番号
    postal_code = models.CharField(max_length=20, blank=True)       # 郵便番号
    address = models.CharField(max_length=255, blank=True)          # 住所
    bus_stop = models.CharField(max_length=100, blank=True)         # バス亭
    bus_number = models.CharField(max_length=50, blank=True)        # バス号

    # Campo auxiliar para referência
    office_cd = models.CharField(max_length=50, blank=True)         # 事業所 (já existe em Employee, mas pode ser útil duplicar aqui)

    def __str__(self):
        return f"{self.employee.employee_id} - {self.apartment_name} {self.room_number}"
