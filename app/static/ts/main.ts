document.addEventListener('DOMContentLoaded', () => {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach((alert) => {
        setTimeout(() => {
            // @ts-ignore
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });

    document.addEventListener('click', (e: MouseEvent) => {
        const target = e.target as HTMLElement;
        const deleteBtn = target.closest('.btn-delete');
        if (deleteBtn && !confirm('Вы уверены, что хотите удалить эту запись?')) {
            e.preventDefault();
        }
    });
});