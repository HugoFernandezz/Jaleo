@echo off
echo ========================================
echo Iniciando en modo DESARROLLO
echo Coleccion: eventos-dev
echo ========================================
set EXPO_PUBLIC_ENV=development
set EXPO_PUBLIC_FIREBASE_COLLECTION=eventos-dev
call npm start

