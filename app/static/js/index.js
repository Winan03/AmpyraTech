console.log("SafyraShield IoT Monitor - Sprint 1");

// Configuración del gráfico
let chart = null;
const UMBRAL_CORRIENTE = 11.0;
const MAX_DATA_POINTS = 20;

// Datos del gráfico
const chartData = {
    labels: [],
    datasets: [
        {
            label: 'LAB-PC-01',
            data: [],
            borderColor: '#3498db',
            backgroundColor: 'rgba(52, 152, 219, 0.1)',
            tension: 0.4,
            fill: true
        },
        {
            label: 'LAB-PC-02',
            data: [],
            borderColor: '#27ae60',
            backgroundColor: 'rgba(39, 174, 96, 0.1)',
            tension: 0.4,
            fill: true
        },
        {
            label: 'LAB-PC-03',
            data: [],
            borderColor: '#9b59b6',
            backgroundColor: 'rgba(155, 89, 182, 0.1)',
            tension: 0.4,
            fill: true
        }
    ]
};

// Inicializar gráfico
function initChart() {
    const ctx = document.getElementById('currentChart').getContext('2d');
    chart = new Chart(ctx, {
        type: 'line',
        data: chartData,
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top'
                },
                tooltip: {
                    mode: 'index',
                    intersect: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    title: {
                        display: true,
                        text: 'Corriente (A)'
                    },
                    ticks: {
                        callback: function(value) {
                            return value.toFixed(1) + ' A';
                        }
                    }
                },
                x: {
                    title: {
                        display: true,
                        text: 'Tiempo'
                    }
                }
            },
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false
            }
        }
    });

    // Agregar línea de umbral
    addThresholdLine();
}

// Agregar línea de umbral al gráfico
function addThresholdLine() {
    if (chart) {
        chart.options.plugins.annotation = {
            annotations: {
                line1: {
                    type: 'line',
                    yMin: UMBRAL_CORRIENTE,
                    yMax: UMBRAL_CORRIENTE,
                    borderColor: '#e74c3c',
                    borderWidth: 2,
                    borderDash: [5, 5],
                    label: {
                        enabled: true,
                        content: 'Umbral: 11.0 A',
                        position: 'end'
                    }
                }
            }
        };
    }
}

// Actualizar datos del gráfico
function updateChart(timestamp) {
    if (!chart) return;

    // Agregar timestamp
    chartData.labels.push(timestamp);
    
    // Limitar a MAX_DATA_POINTS
    if (chartData.labels.length > MAX_DATA_POINTS) {
        chartData.labels.shift();
        chartData.datasets.forEach(dataset => {
            dataset.data.shift();
        });
    }
    
    chart.update('none'); // Actualización sin animación para mejor rendimiento
}

// Formatear números
function formatNumber(num, decimals = 1) {
    return parseFloat(num).toFixed(decimals);
}

// Actualizar tarjeta de sensor
function updateSensorCard(sensor) {
    const card = document.getElementById(`sensor-${sensor.id}`);
    if (!card) return;

    // Actualizar valores
    document.getElementById(`irms-${sensor.id}`).textContent = 
        formatNumber(sensor.irms, 3) + ' A';
    document.getElementById(`power-${sensor.id}`).textContent = 
        formatNumber(sensor.potencia, 2) + ' W';

    // Actualizar barra de progreso
    const percentage = Math.min((sensor.irms / UMBRAL_CORRIENTE) * 100, 100);
    document.getElementById(`progress-${sensor.id}`).style.width = percentage + '%';

    // Aplicar clase de sobrecarga
    if (sensor.is_overload) {
        card.classList.add('overload');
    } else {
        card.classList.remove('overload');
    }

    // Agregar dato al gráfico
    const datasetIndex = ['LAB-PC-01', 'LAB-PC-02', 'LAB-PC-03'].indexOf(sensor.id);
    if (datasetIndex !== -1 && chartData.datasets[datasetIndex]) {
        // Solo agregar si es un nuevo timestamp
        const currentLength = chartData.datasets[datasetIndex].data.length;
        if (currentLength === 0 || currentLength < chartData.labels.length) {
            chartData.datasets[datasetIndex].data.push(sensor.irms);
        } else {
            // Actualizar el último valor
            chartData.datasets[datasetIndex].data[currentLength - 1] = sensor.irms;
        }
    }
}

// Actualizar datos desde la API
async function updateData() {
    try {
        const response = await fetch('/api/data/current');
        const data = await response.json();
        
        // Actualizar estado de conexión
        const statusElement = document.getElementById('connection-status');
        if (statusElement) {
            statusElement.textContent = data.message;
            if (data.connected) {
                statusElement.classList.remove('disconnected');
                statusElement.classList.add('connected');
            } else {
                statusElement.classList.remove('connected');
                statusElement.classList.add('disconnected');
            }
        }
        
        // Timestamp para el gráfico
        const now = new Date();
        const timestamp = now.toLocaleTimeString('es-PE', { 
            hour: '2-digit', 
            minute: '2-digit', 
            second: '2-digit' 
        });
        
        // Actualizar cada sensor
        let needsChartUpdate = false;
        data.sensors.forEach(sensor => {
            updateSensorCard(sensor);
            if (sensor.irms > 0) needsChartUpdate = true;
        });
        
        // Actualizar gráfico solo si hay datos nuevos
        if (needsChartUpdate) {
            updateChart(timestamp);
        }
        
        // Actualizar timestamp de última actualización
        const timestampElement = document.getElementById('last-update');
        if (timestampElement) {
            timestampElement.textContent = `Última actualización: ${timestamp}`;
        }
        
    } catch (error) {
        console.error('Error al actualizar datos:', error);
        
        // Mostrar error en el estado de conexión
        const statusElement = document.getElementById('connection-status');
        if (statusElement) {
            statusElement.textContent = 'Error de conexión';
            statusElement.classList.remove('connected');
            statusElement.classList.add('disconnected');
        }
    }
}

// Inicializar cuando el DOM esté listo
document.addEventListener("DOMContentLoaded", function() {
    console.log('Inicializando SafyraShield - Sprint 1 MVP');
    
    // Inicializar gráfico
    initChart();
    
    // Agregar efectos a las tarjetas
    const cards = document.querySelectorAll('.sensor-card');
    cards.forEach(card => {
        card.addEventListener('click', function() {
            // Efecto visual al hacer click
            this.style.transform = 'scale(0.98)';
            setTimeout(() => {
                this.style.transform = '';
            }, 100);
        });
    });
    
    // Actualizar datos inmediatamente
    updateData();
    
    // Actualizar datos cada 3 segundos (ajustable según necesidad)
    setInterval(updateData, 3000);
    
    console.log('Sistema de monitoreo activo - Actualizando cada 3 segundos');
    console.log('Umbral de sobrecarga configurado en:', UMBRAL_CORRIENTE, 'A');
});