document.addEventListener('DOMContentLoaded', function () {
    // 1. Current Date Display
    const dateEl = document.getElementById('currentDateDisplay');
    if (dateEl) {
        const options = { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric' };
        dateEl.textContent = new Date().toLocaleDateString('en-US', options);
    }

    // 2. Mobile Sidebar Toggle
    const sidebar = document.getElementById('appSidebar');
    const toggleBtn = document.getElementById('sidebarToggle');
    if (toggleBtn && sidebar) {
        toggleBtn.addEventListener('click', function () {
            sidebar.classList.toggle('show');
        });

        // Close when clicking outside on mobile
        document.addEventListener('click', function (e) {
            if (window.innerWidth < 992 && !sidebar.contains(e.target) && !toggleBtn.contains(e.target)) {
                sidebar.classList.remove('show');
            }
        });
    }

    // 3. Global Delete Confirmation Modal Handler
    const confirmDeleteModal = document.getElementById('confirmDeleteModal');
    if (confirmDeleteModal) {
        confirmDeleteModal.addEventListener('show.bs.modal', function (event) {
            const button = event.relatedTarget;
            if (!button) return;

            const actionUrl = button.getAttribute('data-action');
            const itemTitle = button.getAttribute('data-title') || 'this item';
            const message = button.getAttribute('data-message') || `Are you sure you want to delete ${itemTitle}? This action cannot be undone.`;

            const form = document.getElementById('confirmDeleteForm');
            const titleEl = document.getElementById('confirmModalTitle');
            const bodyEl = document.getElementById('confirmModalBody');

            if (form) form.action = actionUrl;
            if (titleEl) titleEl.textContent = `Delete ${itemTitle}`;
            if (bodyEl) bodyEl.textContent = message;
        });
    }

        // Auto‑fill customer details when selecting existing name or phone
    const nameInput = document.querySelector('input[name="customer_name"]');
    const phoneInput = document.querySelector('input[name="customer_phone"]');
    const emailInput = document.querySelector('input[name="customer_email"]');
    const gstinInput = document.querySelector('input[name="customer_gstin"]');
    const addressInput = document.querySelector('textarea[name="customer_address"]');
    const hiddenId = document.getElementById('customerIdInput');

    function fillFromOption(option) {
        if (!option) return;
        const id = option.dataset.id;
        const phone = option.dataset.phone || option.dataset.phone || '';
        const email = option.dataset.email || '';
        const address = option.dataset.address || '';
        const gstin = option.dataset.gstin || '';
        // Set values
        hiddenId.value = id || '';
        if (phone) phoneInput.value = phone;
        if (email) emailInput.value = email;
        if (address) addressInput.value = address;
        if (gstin) gstinInput.value = gstin;
    }

    // When name changes, find matching option in name datalist
    if (nameInput) {
        nameInput.addEventListener('input', function () {
            const val = this.value;
            const opt = document.querySelector(`#customerNames option[value="${val}"]`);
            fillFromOption(opt);
        });
    }

    // When phone changes, find matching option in phone datalist
    if (phoneInput) {
        phoneInput.addEventListener('input', function () {
            const val = this.value;
            const opt = document.querySelector(`#customerPhones option[value="${val}"]`);
            fillFromOption(opt);
        });
    }

  const newCustomerBtn = document.getElementById('newCustomerBtn');
  const newCustomerFields = document.getElementById('newCustomerFields');
  if (newCustomerBtn && newCustomerFields) {
    newCustomerBtn.addEventListener('click', function () {
      newCustomerFields.classList.toggle('d-none');
      // Clear fields when hiding
      if (newCustomerFields.classList.contains('d-none')) {
        newCustomerFields.querySelectorAll('input, textarea').forEach(el => el.value = '');
      }
    });
  }


    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(function (alert) {
        setTimeout(function () {
            const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
            if (bsAlert) {
                bsAlert.close();
            }
        }, 6000);
    });
});
