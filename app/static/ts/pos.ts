interface CartItem {
    id: number;
    name: string;
    price: number;
    quantity: number;
    stock: number;
}

class POSSystem {
    private cart: CartItem[] = [];
    private customerId: number | null = null;

    constructor() {
        this.init();
    }

    private init() {
        document.addEventListener('click', (e) => {
            const target = e.target as HTMLElement;
            
            const addButton = target.closest('.js-add-to-cart');
            
            if (addButton) {
                const id = parseInt(addButton.getAttribute('data-id') || '0');
                const name = addButton.getAttribute('data-name') || '';
                const price = parseFloat(addButton.getAttribute('data-price') || '0');
                const stock = parseInt(addButton.getAttribute('data-stock') || '0');
                
                if (stock <= 0) {
                    alert('Товара нет на складе');
                    return;
                }

                this.addToCart({ id, name, price, stock, quantity: 1 });
            }
        });

        const customerSelect = document.getElementById('customer-select') as HTMLSelectElement;
        if (customerSelect) {
            customerSelect.addEventListener('change', () => {
                this.customerId = customerSelect.value ? parseInt(customerSelect.value) : null;
            });
        }

        const checkoutBtn = document.getElementById('checkout-btn');
        if (checkoutBtn) {
            checkoutBtn.addEventListener('click', () => this.submitSale());
        }
    }

    public addToCart(product: CartItem) {
        const existing = this.cart.find(item => item.id === product.id);
        
        if (existing) {
            if (existing.quantity < product.stock) {
                existing.quantity++;
            } else {
                alert(`Достигнут предел наличия (${product.stock} шт.)`);
            }
        } else {
            this.cart.push(product);
        }
        this.renderCart();
    }

    private renderCart() {
        const container = document.getElementById('cart-items');
        if (!container) return;
        
        if (this.cart.length === 0) {
            container.innerHTML = '<p class="text-muted text-center py-5">Корзина пуста</p>';
        } else {
            container.innerHTML = this.cart.map((item, index) => `
                <div class="d-flex justify-content-between align-items-center mb-3 p-2 border-bottom">
                    <div style="flex-grow: 1;">
                        <div class="fw-bold" style="color: #243B53;">${item.name}</div>
                        <small class="text-muted">${item.price.toLocaleString()} ₽ x ${item.quantity}</small>
                    </div>
                    <div class="d-flex align-items-center">
                        <span class="fw-bold me-3" style="color: #000;">${(item.price * item.quantity).toLocaleString()} ₽</span>
                        <button class="btn btn-sm btn-outline-danger" onclick="posSystem.removeItem(${index})">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>
                </div>
            `).join('');
        }
        
        const total = this.cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
        const totalEl = document.getElementById('total-amount');
        if (totalEl) totalEl.innerText = `${total.toLocaleString(undefined, {minimumFractionDigits: 2})} ₽`;
    }

    public removeItem(index: number) {
        this.cart.splice(index, 1);
        this.renderCart();
    }

    public async submitSale() {
        if (this.cart.length === 0) {
            alert('Сначала добавьте товары в корзину');
            return;
        }

        const payload = {
            customer_id: this.customerId,
            items: this.cart.map(item => ({
                product_id: item.id,
                quantity: item.quantity,
                price: item.price
            })),
            payment_method: (document.getElementById('payment-method') as HTMLSelectElement)?.value || 'карта'
        };

        try {
            const response = await fetch('/manager/api/create-order', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const result = await response.json();
            if (result.success) {
                alert('Продажа успешно оформлена!');
                if (result.sale_id) {
                    window.open(`/manager/sale/${result.sale_id}/receipt`, '_blank');
                }
                location.reload();
            } else {
                alert('Ошибка: ' + (result.error || 'Неизвестная ошибка'));
            }
        } catch (e) {
            alert('Ошибка связи с сервером');
        }
    }
}

const posSystem = new POSSystem();
(window as any).posSystem = posSystem;