class NgrokMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # Agregar header para saltar advertencia de ngrok
        response['ngrok-skip-browser-warning'] = 'true'
        return response