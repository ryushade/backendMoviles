# Backend moviles

## Entorno virtual
```
python3 -m venv .venv
.venv\Scripts\activate
$env:PYTHONDONTWRITEBYTECODE=1
```

## Dependencias
```
pip install Flask==2.3.3
pip install flask-jwt-extended
pip install PyMySql
pip install bcrypt
pip install stripe
pip install firebase-admin
pip install google-api-python-client
```

## Iniciar Proyecto
```
set FLASK_ENV=development
flask --app main run
```

