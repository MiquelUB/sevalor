Now I have a comprehensive understanding of the repository. Let me compile a complete security audit with detailed findings and recommendations.

## Auditoria de Seguridad del Código - SEVALOR

He realizado una auditoría completa de seguridad del repositorio **MiquelUB/sevalor**, una plataforma **SaaS multi-tenant para gestión de equipos y operaciones** (SEVALOR Suite). Aquí está el análisis estructurado:

---

## 📊 Resumen Ejecutivo

| Aspecto | Estado | Severidad |
|--------|--------|-----------|
| **Arquitectura Multi-Tenant (RLS)** | ✅ Implementado | Bajo |
| **Control de Acceso por Roles (RBAC)** | 🔴 Crítico | **CRÍTICA** |
| **Seguridad de Datos Financieros** | 🔴 Crítico | **CRÍTICA** |
| **Validación de Entrada** | 🟡 Parcial | Media |
| **Gestión de Secretos** | ✅ Buena (env vars) | Bajo |
| **Criptografía** | 🟡 Parcial | Media |
| **Autenticación** | 🟡 Incompleta | Media |
| **Tests de Seguridad** | 🔴 Insuficientes | **CRÍTICA** |

---

## 🔴 HALLAZGOS CRÍTICOS

### **CR-01: Ausencia de RBAC en `/gestio`**

**Ubicación:** `backend/app/api/v1/gestio/*.py` (clientes, proveedores, almacén, facturación, etc.)

**Problema:** La mayoría de endpoints verifican únicamente `request.state.empresa_id`. Un operario de campo con rol `OPERARI` puede:
- Crear/editar clientes y proveedores
- Crear facturas sin privilegios financieros
- Acceder a datos bancarios (IBAN)
- Modificar datos de flota y vehículos

```python
# ❌ INSEGURO - backend/app/api/v1/gestio/clients.py
@router.post("/clients", response_model=ClientResponse)
async def crear_client(request: Request, payload: ClientCreate, db: AsyncSession = Depends(get_db_with_tenant_context)):
    empresa_id = request.state.empresa_id  # ← Sin verificación de rol
    # Un OPERARI puede ejecutar esto
```

**Impacto:** Violación de Zero-Trust, privacidad de datos financieros comprometida, incumplimiento normativo (AEAT).

**Recomendación:**
```python
# ✅ SEGURO
@router.post("/clients", response_model=ClientResponse, 
             dependencies=[Depends(require_roles(["BOSS", "SECRETARIA"]))])
async def crear_client(
    request: Request,
    payload: ClientCreate,
    claims: Dict = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    # Solo BOSS y SECRETARIA pueden crear clientes
    ...
```

---

### **CR-02: Facturación Veri*factu Incompleta e Insegura**

**Ubicación:** `backend/app/api/v1/gestio/comptabilitat.py:63-168`

**Problemas:**

1. **Sin restricción de rol financiero:**
```python
@router.post("/factures", response_model=FacturaResponse, status_code=status.HTTP_201_CREATED)
async def crear_factura(request: Request, payload: FacturaCreate, db: AsyncSession):
    # Línea 20 declara dependency pero no se aplica correctamente
    # Falta validación de que user.rol == "BOSS" o "COMPTABILITAT"
```

2. **Hash SHA-256 incorrecto (incumple RD 1619/2012):**
```python
# ❌ El hash debe incluir TODOS los campos immutables
hash_actual = resultat_pdf["hash_sha256"]  # Generado en verifactu.py pero sin validación
# Falta: serie + numero + base + iva + fecha + cliente_nif + hash_anterior
```

3. **Servicios Veri*factu no existen:**
```python
from app.services.verifactu import generar_factura_pdf  # ❌ No existe
from app.services.outbox_aeat import registrar_enviament_outbox  # ❌ No existe
```

**Impacto:** Facturas legalmente inválidas, sin trail de auditoría, incumplimiento AEAT.

**Recomendación:**
```python
# Implementar validación completa
@router.post("/factures", dependencies=[Depends(require_financial_access)])
async def crear_factura(
    request: Request,
    payload: FacturaCreate,
    claims: Dict = Depends(get_current_user_claims),
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    # 1. Verificar rol financiero (ya en dependency)
    # 2. Calcular hash encadenado
    # 3. Generar PDF con QR (Veri*factu)
    # 4. Registrar en outbox para AEAT
    # 5. Persistir con audit trail
```

---

### **CR-03: Duplicación de Columnas en ORM**

**Ubicación:** `backend/app/models/models.py:51-52, 58-59, 754-760`

**Problema:**
```python
class Empresa(Base):
    __tablename__ = "empreses"
    
    # ❌ Definido dos veces
    node_ia_url: str = Column(String)  # Línea 51
    node_ia_url: str = Column(String)  # Línea 58 - DUPLICADO
    
    node_ia_actiu: bool = Column(Boolean)  # Línea 52
    node_ia_actiu: bool = Column(Boolean)  # Línea 59 - DUPLICADO

class ConsultaXatCopilot(Base):
    # ❌ Copia atributos que no le pertenecen
    feature_copilot_ia: bool  # Debe estar en Empresa, no aquí
    feature_flota: bool
```

**Impacto:** Fallos de SQLAlchemy, mypy reporta 11 errores, aplicación puede no iniciar.

**Recomendación:**
```python
class Empresa(Base):
    __tablename__ = "empreses"
    node_ia_url: str = Column(String, nullable=True)  # Una sola vez
    node_ia_actiu: bool = Column(Boolean, default=False)

class ConsultaXatCopilot(Base):
    # Solo atributos relevantes a consultas
    id: UUID = Column(UUID, primary_key=True)
    pregunta: str = Column(String)
    resposta: str = Column(String)
    temps_inferencia: float
```

---

### **CR-04: Workers Celery con Imports Inexistentes**

**Ubicación:** `backend/app/workers/tasks.py:12-15`

**Problema:**
```python
from app.services.verifactu import task_facturacio_aeat  # ❌ NO EXISTE
from app.services.backup import task_backup_setmanal  # ❌ NO EXISTE
from app.services.outbox_aeat import procesar_outbox  # ❌ NO EXISTE
from app.services.whisper_service import transcribir_audio  # ❌ NO EXISTE
```

**Impacto:** 
- Toda la facturación asíncrona falla
- Backups no se ejecutan
- Transcripción de audio no funciona
- Cola Celery se colapsa

**Recomendación:**
Crear los módulos faltantes:
```python
# backend/app/services/verifactu.py
async def generar_factura_pdf(db, empresa_id, ...):
    """Genera PDF Veri*factu con QR y hash encadenado"""
    # Implementar lógica completa
    
# backend/app/services/outbox_aeat.py
async def registrar_enviament_outbox(factura_id, ...):
    """Patrón Outbox para AEAT"""
```

---

### **CR-05: Router PWA de Picking Incompleto**

**Ubicación:** `backend/app/api/v1/operari_pwa/picking.py`

**Problema:** Solo existe `PUT /operari/picking/linies/{linia_id}`. Faltan:
- `POST /operari/picking` - crear hoja de picking
- `POST /operari/picking/{id}/linies` - añadir líneas
- `GET /operari/picking/{id}` - obtener detalles
- `DELETE /operari/picking/{id}/linies/{linia_id}` - eliminar línea

**Impacto:** Test falla (`404 != 201`), PWA no puede realizar picking.

---

## 🟡 HALLAZGOS ALTOS (Importantes)

### **ALT-01: Duplicación JWT en Routers PWA**

**Ubicación:** `backend/app/api/v1/operari_pwa/jornada.py`, `incidencies.py`

**Problema:** Cada router decodifica Bearer token inline en lugar de usar `get_current_user_claims`:

```python
# ❌ DUPLICADO en cada endpoint
auth_header = request.headers.get("Authorization")
token = auth_header.split(" ")[1]
payload = jwt.decode(token, settings.SECRET_KEY, ...)
```

**Recomendación:**
```python
# Crear dependencia reutilizable
def get_current_operari(
    claims: Dict = Depends(get_current_user_claims)
) -> Dict:
    """Extrae claims del operario y valida que sea OPERARI"""
    if claims.get("rol", "").upper() != "OPERARI":
        raise HTTPException(status_code=403, detail="Solo operarios")
    return claims

# Usar en todos los endpoints PWA
@router.post("/jornada")
async def crear_jornada(
    claims: Dict = Depends(get_current_operari),
    db: AsyncSession = Depends(get_db_with_tenant_context)
):
    operari_id = claims["sub"]
    ...
```

---

### **ALT-02: Jornada sin Verificación de Ownership**

**Ubicación:** `backend/app/api/v1/operari_pwa/jornada.py:95-126`

```python
@router.post("/{jornada_id}/fi")
async def terminar_jornada(jornada_id: str, ...):
    stmt = select(RegistreJornadaLaboral).where(
        RegistreJornadaLaboral.id == jornada_id
        # ❌ Falta: RegistreJornadaLaboral.usuari_id == claims["sub"]
    )
    # Un operario puede cerrar la jornada de otro
```

**Recomendación:**
```python
stmt = select(RegistreJornadaLaboral).where(
    RegistreJornadaLaboral.id == jornada_id,
    RegistreJornadaLaboral.usuari_id == claims["sub"],  # ✅ Ownership check
    RegistreJornadaLaboral.empresa_id == claims["empresa_id"]
)
```

---

### **ALT-03: Onboarding de Tenants Incompleto**

**Ubicación:** `backend/app/api/v1/superadmin/tenants.py`

**Faltan:**
- Flujo 2FA TOTP obligatorio
- Token de activación de un solo uso
- Email de bienvenida
- Inicialización de directorio en Celery
- Validación de IP allowlist

---

### **ALT-04: Superadmin sin Protecciones Adicionales**

**Problema:** Token SUPERADMIN robado = acceso a TODOS los datos.

**Recomendación:**
```python
# 1. IP Allowlist para SUPERADMIN
# 2. 2FA TOTP obligatorio
# 3. Blacklist de tokens en Redis
# 4. Audit logging de todas las acciones
```

---

## 📋 Validación de Entrada

| Aspecto | Estado | Recomendación |
|--------|--------|---------------|
| **Email validation** | ✅ Pydantic `EmailStr` | Usar en todos los modelos |
| **UUID validation** | ✅ `uuid.UUID` | OK |
| **File upload** | 🔴 Falta `filetype` check | Verificar magic bytes (no extension) |
| **SQL Injection** | ✅ SQLAlchemy + parameterized | OK (async + prepared statements) |
| **XSS** | ✅ Bleach en imports | Verificar uso en serialización HTML |
| **CORS** | 🟡 Muy permisivo | Restringir a dominios específicos |

---

## 🔐 Criptografía y Secretos

| Aspecto | Estado | Detalle |
|--------|--------|--------|
| **Almacenamiento de secretos** | ✅ Variables de entorno | Correcto, `.env` no versionado |
| **Hashing de contraseñas** | ✅ bcrypt | Via `passlib[bcrypt]` |
| **JWT** | ⚠️ Verificación débil | `options={"verify_aud": False}` permite bypass |
| **HTTPS/SSL** | ✅ Nginx + Let's Encrypt | En `infra/nginx` |
| **Row-Level Security** | ✅ PostgreSQL RLS | Política `FORCE` correcta |

**Problema JWT:**
```python
# ❌ Inseguro
payload = jwt.decode(token, settings.SECRET_KEY, 
                     options={"verify_aud": False})  # Bypass deshabilitado
```

**Recomendación:**
```python
# ✅ Seguro
payload = jwt.decode(token, settings.SECRET_KEY, 
                     algorithms=[settings.ALGORITHM],
                     audience="sevalor-app")  # Verificar audience
```

---

## 🧪 Testing de Seguridad

**Problemas:**
- `test_rls_middleware.py` termina con `pass` sin assertions
- No hay tests de rols (RBAC)
- No hay tests de validación de entrada
- No hay tests de injection (SQL, XSS)

**Recomendación:** Crear `backend/tests/test_security.py`:
```python
async def test_operari_cannot_access_comptabilitat():
    """Operari NO puede acceder a /gestio/comptabilitat"""
    token = create_test_token(rol="OPERARI")
    response = client.get("/api/v1/gestio/comptabilitat/factures",
                          headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403

async def test_operari_cannot_create_client():
    """Operari NO puede crear cliente"""
    response = client.post("/api/v1/gestio/clients", json=..., 
                          headers={"Authorization": f"Bearer {operari_token}"})
    assert response.status_code == 403

async def test_tenant_isolation():
    """Tenant A no puede acceder a datos de Tenant B"""
    # Implementar test con dos tenants
    pass
```

---

## 🏗️ Configuración y Stack

**Docker Compose Security:**
```yaml
# ✅ Bueno
security_opt:
  - no-new-privileges:true
user: "1000:1000"  # No root
tmpfs:
  - /tmp            # /tmp en memoria, no disco
```

**Middleware:**
```python
# app/middleware/tenant.py
# ✅ Implementa context de tenant
# ⚠️ Falta validación de capçalera X-Empresa-ID contra JWT
```

---

## 📝 Recomendaciones Prioridad 1 (CRÍTICA)

1. **Aplicar RBAC en todos los endpoints** de `/gestio`
   - Usar `@router.post(..., dependencies=[Depends(require_financial_access)])`
   - Crear `require_roles` específicas por dominio

2. **Implementar servicios Veri*factu**
   - `app/services/verifactu.py` con PDF + QR + hash encadenado
   - `app/services/outbox_aeat.py` con patrón Outbox

3. **Arreglar modelo ORM**
   - Eliminar columnas duplicadas en `Empresa`
   - Simplificar `ConsultaXatCopilot`

4. **Expandir tests de seguridad**
   - Tests de RBAC por rol
   - Tests de tenant isolation
   - Tests de validación de entrada

5. **Completar PWA routers**
   - Picking: POST/GET/DELETE
   - Jornada: verificación de ownership
   - Incidencias: permisos por estado

---

## 📝 Checklist de Remedición

- [ ] RBAC en `/gestio/*` (clientes, proveedores, almacén, comptabilitat)
- [ ] Veri*factu con PDF + QR + AEAT
- [ ] Modelo ORM sin duplicaciones
- [ ] 2FA TOTP para SUPERADMIN
- [ ] Validación de archivos (magic bytes)
- [ ] Tests de seguridad (RBAC, tenant isolation)
- [ ] IP Allowlist para SUPERADMIN
- [ ] Audit logging de acciones financieras
- [ ] JWT con audience claim
- [ ] Rate limiting en endpoints sensibles

---

¿Quieres que profundice en algún área específica o que cree PRs para remediar los hallazgos críticos?