# Instalador para Windows

El instalador se construye para Windows 10/11 de 64 bits y deja una aplicación
autocontenida. El computador donde se instala no necesita Python, pip, Chrome,
Selenium, Playwright ni Chromium: la verificación de Alfresco es por API REST.

## Construcción

Ejecute PowerShell desde la raíz del proyecto:

```powershell
powershell -ExecutionPolicy Bypass -File .\build_gui.ps1
```

El script crea un entorno de compilación, instala `requirements.txt` y
`requirements-gui.txt`, empaqueta la GUI con PyInstaller y compila el instalador
con Inno Setup. El paquete ya no incluye Selenium, Playwright ni Chromium.

El resultado queda en:

```text
installer_output\Setup_ContratacionesETL_1.0.0.exe
```

Al instalar, el acceso directo abre directamente la GUI equivalente a:

```text
python -m desktop
```

En el primer inicio, las credenciales se pueden guardar desde la pantalla
**Configuración**. La URL y el usuario se guardan en la configuración local y la
contraseña se almacena en el Administrador de credenciales de Windows. Después
no es necesario volver a digitarlas. El archivo `.env` continúa siendo opcional
y funciona como respaldo para instalaciones existentes; el instalador no
contiene credenciales reales.

## Backend de Alfresco

La aplicación usa el backend **MCP/REST** (`--backend-alfresco mcp`, por
defecto), que solo requiere acceso de red a Alfresco y las credenciales
guardadas en Configuración o en `.env`. El backend legado con Selenium (`--backend-alfresco selenium`) queda
disponible únicamente en el entorno de desarrollo, donde sí están instaladas
las dependencias de scraping.
