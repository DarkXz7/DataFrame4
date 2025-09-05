// JavaScript para manejar la previsualización de archivos SQL
document.addEventListener('DOMContentLoaded', function() {
  // Mostrar el botón de previsualización solo cuando se selecciona modo "compartido"
  const modoCompartido = document.getElementById('modo_compartido');
  const modoLocal = document.getElementById('modo_local');
  const prevContainer = document.getElementById('vista_previa_contenedor');
  const btnPrevisualizar = document.getElementById('btn_previsualizar');
  const cargando = document.getElementById('cargando');
  const previewResult = document.getElementById('preview_result');
  
  function updatePreviewVisibility() {
    prevContainer.style.display = modoCompartido.checked ? 'block' : 'none';
  }
  
  modoCompartido.addEventListener('change', updatePreviewVisibility);
  modoLocal.addEventListener('change', updatePreviewVisibility);
  updatePreviewVisibility();
  
  // Manejar clic en el botón de previsualizar
  btnPrevisualizar.addEventListener('click', function() {
    const ruta = document.querySelector('input[name="ruta_compartida"]').value.trim();
    const archivo = document.querySelector('input[name="nombre_archivo"]').value.trim();
    
    if (!ruta || !archivo) {
      previewResult.innerHTML = '<div class="alert alert-warning">Por favor, ingresa la ruta y el nombre del archivo.</div>';
      return;
    }
    
    if (!archivo.toLowerCase().endsWith('.sql')) {
      previewResult.innerHTML = '<div class="alert alert-warning">El archivo debe tener extensión .sql</div>';
      return;
    }
    
    // Mostrar indicador de carga
    cargando.style.display = 'block';
    previewResult.innerHTML = '';
    
    // Realizar petición AJAX
    fetch('/api/preview-sql-estructura/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
      },
      body: JSON.stringify({
        ruta: ruta,
        archivo: archivo
      })
    })
    .then(response => response.json())
    .then(data => {
      cargando.style.display = 'none';
      
      if (!data.ok) {
        previewResult.innerHTML = `<div class="alert alert-danger">${data.error}</div>`;
        return;
      }
      
      if (data.tablas.length === 0) {
        previewResult.innerHTML = `<div class="alert alert-warning">No se encontraron tablas en el archivo SQL.</div>`;
        return;
      }
      
      // Mostrar resultado
      let html = `
        <div class="card border-info">
          <div class="card-header bg-info text-white">
            <h5><i class="bi bi-table"></i> Tablas encontradas en el archivo</h5>
          </div>
          <div class="card-body">
            <div class="mb-3">
              <strong>${data.tablas.length} tabla(s) detectada(s)</strong>
            </div>
            <div class="table-responsive">
              <table class="table table-sm table-hover">
                <thead>
                  <tr>
                    <th>Tabla</th>
                    <th>Columnas</th>
                    <th>Acciones</th>
                  </tr>
                </thead>
                <tbody>`;
      
      data.tablas.forEach(tabla => {
        html += `
          <tr>
            <td>${tabla.nombre}</td>
            <td>${tabla.columnas?.join(', ') || 'No disponible'}</td>
            <td>
              <button type="button" class="btn btn-sm btn-outline-primary" 
                onclick="mostrarDetallesTabla('${tabla.nombre}')">
                <i class="bi bi-eye"></i> Detalles
              </button>
            </td>
          </tr>`;
      });
      
      html += `
                </tbody>
              </table>
            </div>
          </div>
        </div>
        
        <div class="mt-3 text-end">
          <button type="submit" name="accion" value="subir_archivo" class="btn btn-primary">
            <i class="bi bi-arrow-right"></i> Continuar con estas tablas
          </button>
        </div>`;
      
      previewResult.innerHTML = html;
      
      // Guardar datos en localStorage para uso posterior
      localStorage.setItem('sql_preview_data', JSON.stringify(data));
    })
    .catch(error => {
      cargando.style.display = 'none';
      previewResult.innerHTML = `<div class="alert alert-danger">Error de comunicación: ${error}</div>`;
    });
  });
});

// Función para mostrar detalles de tabla en modal
function mostrarDetallesTabla(tabla) {
  const data = JSON.parse(localStorage.getItem('sql_preview_data'));
  const tablaInfo = data.tablas.find(t => t.nombre === tabla);
  
  // Modal HTML
  const modalHTML = `
    <div class="modal fade" id="detallesTablaModal" tabindex="-1">
      <div class="modal-dialog modal-lg">
        <div class="modal-content">
          <div class="modal-header bg-primary text-white">
            <h5 class="modal-title"><i class="bi bi-table"></i> Tabla: ${tabla}</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
          </div>
          <div class="modal-body">
            <h6>Columnas:</h6>
            <div class="table-responsive">
              <table class="table table-sm">
                <thead>
                  <tr>
                    <th>Nombre</th>
                    <th>Tipo</th>
                  </tr>
                </thead>
                <tbody>
                  ${tablaInfo.columnas_info?.map(col => `
                    <tr>
                      <td>${col.nombre}</td>
                      <td>${col.tipo || 'N/A'}</td>
                    </tr>
                  `).join('') || '<tr><td colspan="2">Información detallada no disponible</td></tr>'}
                </tbody>
              </table>
            </div>
            ${tablaInfo.preview ? `
              <h6 class="mt-3">Vista previa de datos:</h6>
              <div class="table-responsive">
                <table class="table table-sm table-striped">
                  <thead>
                    <tr>
                      ${tablaInfo.columnas?.map(col => `<th>${col}</th>`).join('') || ''}
                    </tr>
                  </thead>
                  <tbody>
                    ${tablaInfo.preview?.map(row => `
                      <tr>
                        ${row.map(cell => `<td>${cell === null ? '' : cell}</td>`).join('')}
                      </tr>
                    `).join('') || ''}
                  </tbody>
                </table>
              </div>
            ` : ''}
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Cerrar</button>
          </div>
        </div>
      </div>
    </div>`;

  // Insertar modal en el DOM
  const modalContainer = document.createElement('div');
  modalContainer.innerHTML = modalHTML;
  document.body.appendChild(modalContainer);
  
  // Mostrar modal
  const modal = new bootstrap.Modal(document.getElementById('detallesTablaModal'));
  modal.show();
  
  // Limpiar el DOM cuando se cierre
  document.getElementById('detallesTablaModal').addEventListener('hidden.bs.modal', function() {
    document.body.removeChild(modalContainer);
  });
}