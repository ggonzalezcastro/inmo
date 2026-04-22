class DealError(Exception):
    """Base deal error."""

    def __init__(self, message: str, status_code: int = 400):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class DealConflictError(DealError):
    """Raised when trying to create a deal for a property that's already reserved/sold."""

    def __init__(self, property_id: int):
        super().__init__(
            f"La propiedad {property_id} ya tiene un deal activo o no está disponible.",
            status_code=409,
        )


class DealNotFoundError(DealError):
    def __init__(self, deal_id: int):
        super().__init__(f"Deal {deal_id} no encontrado.", status_code=404)


class DealPermissionError(DealError):
    def __init__(self):
        super().__init__("No tienes permiso para realizar esta acción.", status_code=403)
