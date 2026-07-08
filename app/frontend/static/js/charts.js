/**
 * System Data Visualization Engine
 * Initializes and updates Chart.js instances dynamically.
 */

window.GymCharts = {
    instances: {},

    init() {
        // Standard Global Theming
        Chart.defaults.color = '#9CA3AF';
        Chart.defaults.font.family = "'Inter', sans-serif";
        Chart.defaults.plugins.tooltip.backgroundColor = '#1c1e24';
        Chart.defaults.plugins.tooltip.borderColor = '#2d313c';
        Chart.defaults.plugins.tooltip.borderWidth = 1;

        const noGridOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: { x: { display: false }, y: { display: false } }
        };

        // 1. Sparkline 1: Check-ins Trend
        const s1El = document.getElementById('sparkline1');
        if (s1El) {
            this.instances.sparkline1 = new Chart(s1El.getContext('2d'), {
                type: 'line',
                data: {
                    labels: ['1','2','3','4','5','6','7','8','9','10'],
                    datasets: [{
                        data: [12, 19, 15, 25, 22, 30, 28, 35, 20, 28],
                        borderColor: '#D92D2D', borderWidth: 2, tension: 0.4, pointRadius: 0
                    }]
                }, options: noGridOptions
            });
        }

        // 2. Sparkline 2: Visits Trend
        const s2El = document.getElementById('sparkline2');
        if (s2El) {
            this.instances.sparkline2 = new Chart(s2El.getContext('2d'), {
                type: 'line',
                data: {
                    labels: ['1','2','3','4','5','6','7'],
                    datasets: [{
                        data: [40, 55, 48, 65, 59, 80, 112],
                        borderColor: '#22c55e', borderWidth: 2, tension: 0.4, pointRadius: 0
                    }]
                }, options: noGridOptions
            });
        }

        // 3. Sparkline 3: Duration Trend
        const s3El = document.getElementById('sparkline3');
        if (s3El) {
            this.instances.sparkline3 = new Chart(s3El.getContext('2d'), {
                type: 'line',
                data: {
                    labels: ['1','2','3','4','5','6','7'],
                    datasets: [{
                        data: [60, 65, 75, 70, 85, 90, 92],
                        borderColor: '#3b82f6', borderWidth: 2, tension: 0.4, pointRadius: 0
                    }]
                }, options: noGridOptions
            });
        }

        // 4. Main Bar Chart: Attendance Overview
        const barEl = document.getElementById('barChart');
        if (barEl) {
            this.instances.barChart = new Chart(barEl.getContext('2d'), {
                type: 'bar',
                data: {
                    labels: [],
                    datasets: [{
                        data: [],
                        backgroundColor: '#D92D2D',
                        borderRadius: 2,
                        barThickness: 6
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { 
                            grid: { display: false, drawBorder: false },
                            ticks: { maxRotation: 0, autoSkip: false, font: {size: 10} } 
                        },
                        y: { 
                            grid: { color: '#2d313c', borderDash: [5, 5] },
                            ticks: { maxTicksLimit: 5, font: {size: 10} }
                        }
                    }
                }
            });
        }

        // 5. Visit Frequency Donut
        const pieFreqEl = document.getElementById('pieFreq');
        if (pieFreqEl) {
            this.instances.pieFreq = new Chart(pieFreqEl.getContext('2d'), {
                type: 'doughnut',
                data: {
                    labels: [],
                    datasets: [{
                        data: [],
                        backgroundColor: ['#22c55e', '#6d28d9', '#3b82f6'],
                        borderWidth: 0,
                        cutout: '70%'
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
            });
        }

        // 6. Plan Usage Donut
        const pieUsageEl = document.getElementById('pieUsage');
        if (pieUsageEl) {
            this.instances.pieUsage = new Chart(pieUsageEl.getContext('2d'), {
                type: 'doughnut',
                data: {
                    labels: [],
                    datasets: [{
                        data: [],
                        backgroundColor: ['#22c55e', '#D92D2D', '#6b7280'],
                        borderWidth: 0,
                        cutout: '75%'
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
            });
        }

        // 7. Peak Hours Line Chart
        const linePeakEl = document.getElementById('linePeak');
        if (linePeakEl) {
            const ctx = linePeakEl.getContext('2d');
            let gradient = ctx.createLinearGradient(0, 0, 0, 150);
            gradient.addColorStop(0, 'rgba(217, 45, 45, 0.5)');
            gradient.addColorStop(1, 'rgba(217, 45, 45, 0)');

            this.instances.linePeak = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        data: [],
                        borderColor: '#D92D2D',
                        backgroundColor: gradient,
                        fill: true,
                        borderWidth: 2,
                        tension: 0.4,
                        pointRadius: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { grid: { display: false } },
                        y: { display: false, min: 0 }
                    }
                }
            });
        }

        // 8. Demographics Doughnut (for Global Dashboard)
        const pieDemoEl = document.getElementById('pieDemo');
        if (pieDemoEl) {
            this.instances.pieDemo = new Chart(pieDemoEl.getContext('2d'), {
                type: 'doughnut',
                data: {
                    labels: [],
                    datasets: [{
                        data: [],
                        backgroundColor: ['#3b82f6', '#ec4899'], // blue and pink
                        borderWidth: 0,
                        cutout: '70%'
                    }]
                },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } }
            });
        }
    },

    update(chartsData) {
        if (!chartsData) return;

        // Update barChart
        if (this.instances.barChart && chartsData.bar_checkins) {
            this.instances.barChart.data.labels = chartsData.bar_checkins.labels;
            this.instances.barChart.data.datasets[0].data = chartsData.bar_checkins.values;
            this.instances.barChart.update();
        }

        // Update visit_frequency
        if (this.instances.pieFreq && chartsData.visit_frequency) {
            this.instances.pieFreq.data.labels = chartsData.visit_frequency.labels;
            this.instances.pieFreq.data.datasets[0].data = chartsData.visit_frequency.values;
            this.instances.pieFreq.update();
        }

        // Update plan_usage
        if (this.instances.pieUsage && chartsData.plan_usage) {
            this.instances.pieUsage.data.labels = chartsData.plan_usage.labels;
            this.instances.pieUsage.data.datasets[0].data = chartsData.plan_usage.values;
            this.instances.pieUsage.update();
        }

        // Update peak_hours
        if (this.instances.linePeak && chartsData.peak_hours) {
            this.instances.linePeak.data.labels = chartsData.peak_hours.labels;
            this.instances.linePeak.data.datasets[0].data = chartsData.peak_hours.values;
            this.instances.linePeak.update();
        }

        // Update demographics
        if (this.instances.pieDemo && chartsData.demographics) {
            this.instances.pieDemo.data.labels = chartsData.demographics.labels;
            this.instances.pieDemo.data.datasets[0].data = chartsData.demographics.values;
            this.instances.pieDemo.update();
        }
    }
};

document.addEventListener('DOMContentLoaded', () => {
    window.GymCharts.init();
});