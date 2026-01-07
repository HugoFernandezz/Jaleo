@echo off
echo ========================================
echo Iniciando en modo PRODUCCION
echo Coleccion: eventos
echo ========================================
set EXPO_PUBLIC_ENV=production
set EXPO_PUBLIC_FIREBASE_COLLECTION=eventos
call npm start

