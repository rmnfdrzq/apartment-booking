/**
 * Apartment Booking System — Single Page Application (SPA)
 * Handles client-side workflows:
 *  1. Search & Instant Booking (Guest workflow)
 *  2. Apartment Catalog Management (CRUD - Host workflow)
 *  3. Reservation Management (Modify & Cancel stays)
 */

'use strict';

// -----------------------------------------------------------------------------
// Global Application State
// -----------------------------------------------------------------------------
const state = {
  activeTab: 'search',
  apartments: [],
  apartmentsMap: new Map(),
  bookings: [],
  searchDates: {
    startDate: '',
    endDate: ''
  },
  currentBookingApt: null,
  currentModifyBooking: null
};

// -----------------------------------------------------------------------------
// Utility Functions
// -----------------------------------------------------------------------------

/**
 * Escape HTML special characters to prevent XSS.
 * @param {string|null|undefined} str
 * @returns {string}
 */
function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

/**
 * Format currency amount to EUR standard string.
 * @param {number} amount
 * @returns {string}
 */
function formatCurrency(amount) {
  if (typeof amount !== 'number' || isNaN(amount)) return '€0.00';
  return `€${amount.toFixed(2)}`;
}

/**
 * Format ISO date string (YYYY-MM-DD) to readable format.
 * @param {string} isoDate
 * @returns {string}
 */
function formatDate(isoDate) {
  if (!isoDate) return '—';
  try {
    const parts = isoDate.split('-');
    if (parts.length === 3) {
      const year = parseInt(parts[0], 10);
      const month = parseInt(parts[1], 10) - 1;
      const day = parseInt(parts[2], 10);
      const d = new Date(Date.UTC(year, month, day));
      return d.toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
        timeZone: 'UTC'
      });
    }
    return isoDate;
  } catch (e) {
    return isoDate;
  }
}

/**
 * Calculate difference in nights between two YYYY-MM-DD date strings.
 * Returns 0 if either is missing or if endDate <= startDate.
 * @param {string} startDate
 * @param {string} endDate
 * @returns {number}
 */
function calculateNights(startDate, endDate) {
  if (!startDate || !endDate) return 0;
  const d1 = new Date(startDate + 'T00:00:00Z');
  const d2 = new Date(endDate + 'T00:00:00Z');
  const diffTime = d2.getTime() - d1.getTime();
  const diffDays = Math.round(diffTime / (1000 * 3600 * 24));
  return diffDays > 0 ? diffDays : 0;
}

/**
 * Format tomorrow's date as YYYY-MM-DD.
 * @param {number} daysOffset
 * @returns {string}
 */
function getDateOffset(daysOffset = 0) {
  const d = new Date();
  d.setDate(d.getDate() + daysOffset);
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/**
 * Generic API client with JSON parsing and normalized error handling.
 * @param {string} url
 * @param {RequestInit} [options={}]
 * @returns {Promise<any>}
 */
async function apiCall(url, options = {}) {
  const defaultHeaders = {
    'Accept': 'application/json'
  };

  if (options.body && typeof options.body === 'string') {
    defaultHeaders['Content-Type'] = 'application/json';
  }

  const mergedOptions = {
    ...options,
    headers: {
      ...defaultHeaders,
      ...(options.headers || {})
    }
  };

  const response = await fetch(url, mergedOptions);

  if (response.status === 204) {
    return null;
  }

  let data = null;
  const contentType = response.headers.get('content-type') || '';
  if (contentType.includes('application/json')) {
    try {
      data = await response.json();
    } catch (e) {
      // Non-parseable JSON
    }
  }

  if (!response.ok) {
    let errorMessage = `Request failed with status ${response.status}`;
    if (data && data.detail) {
      if (typeof data.detail === 'string') {
        errorMessage = data.detail;
      } else if (Array.isArray(data.detail)) {
        errorMessage = data.detail
          .map(err => {
            const field = err.loc ? err.loc.join('.') : 'field';
            return `${field}: ${err.msg}`;
          })
          .join('; ');
      }
    }
    const error = new Error(errorMessage);
    error.status = response.status;
    error.data = data;
    throw error;
  }

  return data;
}

/**
 * Display a floating toast notification.
 * @param {string} message
 * @param {'success'|'danger'|'warning'|'info'} [type='info']
 * @param {number} [duration=4000]
 */
function showToast(message, type = 'info', duration = 4000) {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const icons = {
    success: '✓',
    danger: '✕',
    warning: '⚠',
    info: 'ℹ'
  };

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.innerHTML = `
    <span class="toast-icon">${icons[type] || 'ℹ'}</span>
    <div class="toast-message">${escapeHtml(message)}</div>
    <button class="toast-close" aria-label="Close">&times;</button>
  `;

  const closeBtn = toast.querySelector('.toast-close');
  const removeToast = () => {
    toast.style.animation = 'slideOut 0.25s forwards';
    setTimeout(() => {
      if (toast.parentElement) toast.remove();
    }, 250);
  };

  closeBtn.addEventListener('click', removeToast);

  container.appendChild(toast);

  if (duration > 0) {
    setTimeout(removeToast, duration);
  }
}

// -----------------------------------------------------------------------------
// Modal Dialog Management
// -----------------------------------------------------------------------------

/**
 * Open a modal dialog by ID.
 * @param {string} modalId
 */
function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (!modal) return;
  modal.style.display = 'flex';
  document.body.style.overflow = 'hidden';

  // Clear modal error messages
  const errorContainers = modal.querySelectorAll('.alert-danger, .inline-error');
  errorContainers.forEach(el => {
    el.style.display = 'none';
    el.textContent = '';
  });

  // Focus first input
  const firstInput = modal.querySelector('input:not([type="hidden"]), select, textarea');
  if (firstInput) {
    setTimeout(() => firstInput.focus(), 50);
  }
}

/**
 * Close a modal dialog by ID.
 * @param {string} modalId
 */
function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (!modal) return;
  modal.style.display = 'none';
  document.body.style.overflow = '';
}

/**
 * Setup modal close listeners.
 */
function setupModalEvents() {
  document.querySelectorAll('[data-close-modal]').forEach(btn => {
    btn.addEventListener('click', () => {
      const modalId = btn.getAttribute('data-close-modal');
      closeModal(modalId);
    });
  });

  // Close when clicking modal backdrop outside dialog
  document.querySelectorAll('.modal-backdrop').forEach(backdrop => {
    backdrop.addEventListener('click', (e) => {
      if (e.target === backdrop) {
        closeModal(backdrop.id);
      }
    });
  });

  // Close on Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal-backdrop').forEach(modal => {
        if (modal.style.display === 'flex') {
          closeModal(modal.id);
        }
      });
    }
  });
}

// -----------------------------------------------------------------------------
// Tab Navigation
// -----------------------------------------------------------------------------

function setupTabNavigation() {
  const tabButtons = document.querySelectorAll('.nav-tab');
  tabButtons.forEach(button => {
    button.addEventListener('click', () => {
      const tabTarget = button.getAttribute('data-tab');
      switchTab(tabTarget);
    });
  });
}

function switchTab(tabName) {
  state.activeTab = tabName;

  document.querySelectorAll('.nav-tab').forEach(btn => {
    const isTarget = btn.getAttribute('data-tab') === tabName;
    btn.classList.toggle('active', isTarget);
    btn.setAttribute('aria-selected', isTarget ? 'true' : 'false');
  });

  document.querySelectorAll('.tab-view').forEach(view => {
    const isTarget = view.id === `view-${tabName}`;
    view.classList.toggle('active', isTarget);
  });

  // Lazy refresh data on tab switch
  if (tabName === 'apartments') {
    loadApartments();
  } else if (tabName === 'bookings') {
    loadBookings();
    loadApartments(); // for filter dropdown
  }
}

// -----------------------------------------------------------------------------
// Workflow 1: Search & Book Apartments
// -----------------------------------------------------------------------------

function setupSearchWorkflow() {
  const searchForm = document.getElementById('search-form');
  const startDateInput = document.getElementById('search-start-date');
  const endDateInput = document.getElementById('search-end-date');

  // Initialize sensible defaults: tomorrow -> 3 nights later
  const defaultStart = getDateOffset(1);
  const defaultEnd = getDateOffset(4);

  startDateInput.value = defaultStart;
  startDateInput.min = getDateOffset(0);
  endDateInput.value = defaultEnd;
  endDateInput.min = defaultStart;

  startDateInput.addEventListener('change', () => {
    if (endDateInput.value && endDateInput.value <= startDateInput.value) {
      const nextDay = new Date(startDateInput.value);
      nextDay.setDate(nextDay.getDate() + 1);
      endDateInput.value = nextDay.toISOString().split('T')[0];
    }
    endDateInput.min = startDateInput.value;
  });

  searchForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    await performSearch();
  });

  // Live price calculation in Booking Modal
  const bookStartInput = document.getElementById('book-start-date');
  const bookEndInput = document.getElementById('book-end-date');

  const updateBookingModalPrice = () => {
    if (!state.currentBookingApt) return;
    const startVal = bookStartInput.value;
    const endVal = bookEndInput.value;
    const nights = calculateNights(startVal, endVal);
    const durationEl = document.getElementById('book-duration');
    const rateEl = document.getElementById('book-rate');
    const totalEl = document.getElementById('book-total-price');

    rateEl.textContent = `${formatCurrency(state.currentBookingApt.price_per_night)} / night`;

    if (nights > 0) {
      durationEl.textContent = `${nights} night${nights === 1 ? '' : 's'}`;
      const totalPrice = nights * state.currentBookingApt.price_per_night;
      totalEl.textContent = formatCurrency(totalPrice);
    } else {
      durationEl.textContent = 'Invalid stay dates (check-out must be after check-in)';
      totalEl.textContent = '—';
    }
  };

  bookStartInput.addEventListener('input', updateBookingModalPrice);
  bookEndInput.addEventListener('input', updateBookingModalPrice);

  // Submit Booking Form
  const bookingForm = document.getElementById('form-create-booking');
  bookingForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    await handleCreateBooking();
  });
}

async function performSearch() {
  const startDate = document.getElementById('search-start-date').value;
  const endDate = document.getElementById('search-end-date').value;
  const errorContainer = document.getElementById('search-error');
  const resultsGrid = document.getElementById('search-results-grid');
  const resultsCount = document.getElementById('search-results-count');
  const searchBtn = document.getElementById('btn-search');

  errorContainer.style.display = 'none';
  errorContainer.textContent = '';

  if (!startDate || !endDate) {
    errorContainer.textContent = 'Please choose both check-in and check-out dates.';
    errorContainer.style.display = 'block';
    return;
  }

  if (endDate <= startDate) {
    errorContainer.textContent = 'Check-out date must be strictly after check-in date.';
    errorContainer.style.display = 'block';
    return;
  }

  state.searchDates = { startDate, endDate };
  const nights = calculateNights(startDate, endDate);

  searchBtn.disabled = true;
  searchBtn.innerHTML = '<span>Searching...</span>';
  resultsGrid.innerHTML = '<div class="loading-state">Searching for available apartments...</div>';

  try {
    const url = `/apartments/search?start_date=${encodeURIComponent(startDate)}&end_date=${encodeURIComponent(endDate)}`;
    const results = await apiCall(url);

    resultsCount.textContent = `${results.length} available for ${nights} night${nights === 1 ? '' : 's'}`;

    if (results.length === 0) {
      resultsGrid.innerHTML = `
        <div class="empty-state">
          <span class="empty-icon">🏖</span>
          <p><strong>No apartments available</strong> for the selected dates (${formatDate(startDate)} – ${formatDate(endDate)}).</p>
          <p class="text-muted">Try adjusting your dates or check back later.</p>
        </div>
      `;
      return;
    }

    resultsGrid.innerHTML = results.map(apt => {
      const totalPrice = nights * apt.price_per_night;
      return `
        <div class="card apartment-card" data-apartment-id="${apt.id}">
          <div class="card-header">
            <h4 class="card-title">${escapeHtml(apt.title)}</h4>
            <span class="badge badge-primary">ID #${apt.id}</span>
          </div>
          <div class="card-body">
            <div class="card-meta">
              <span class="meta-item"><span class="meta-icon">📍</span> ${escapeHtml(apt.address)}</span>
              <span class="meta-item"><span class="meta-icon">👥</span> Max ${apt.max_guests} guests</span>
            </div>
            ${apt.description ? `<p class="card-description">${escapeHtml(apt.description)}</p>` : ''}
            <div class="card-pricing">
              <div class="nightly-rate">
                <span class="rate-amount">${formatCurrency(apt.price_per_night)}</span>
                <span class="rate-unit">/ night</span>
              </div>
              <div class="stay-total">
                <span class="total-label">Total (${nights} night${nights === 1 ? '' : 's'}):</span>
                <span class="total-amount">${formatCurrency(totalPrice)}</span>
              </div>
            </div>
          </div>
          <div class="card-footer">
            <button class="btn btn-primary btn-block btn-book-apartment" data-apt-id="${apt.id}">
              <span>Book This Stay</span>
            </button>
          </div>
        </div>
      `;
    }).join('');

    // Attach click listeners to "Book This Stay" buttons
    resultsGrid.querySelectorAll('.btn-book-apartment').forEach(btn => {
      btn.addEventListener('click', () => {
        const aptId = parseInt(btn.getAttribute('data-apt-id'), 10);
        const apt = results.find(a => a.id === aptId);
        if (apt) {
          openBookingModal(apt, startDate, endDate);
        }
      });
    });

  } catch (err) {
    resultsCount.textContent = 'Search failed';
    resultsGrid.innerHTML = `
      <div class="alert alert-danger">
        Failed to search apartments: ${escapeHtml(err.message)}
      </div>
    `;
  } finally {
    searchBtn.disabled = false;
    searchBtn.innerHTML = '<span>Search Available</span>';
  }
}

/**
 * Open Booking Modal for a specific apartment and date range.
 * @param {object} apartment
 * @param {string} startDate
 * @param {string} endDate
 */
function openBookingModal(apartment, startDate, endDate) {
  state.currentBookingApt = apartment;

  document.getElementById('modal-booking-title').textContent = `Book: ${apartment.title}`;
  document.getElementById('book-apartment-id').value = apartment.id;

  const summaryEl = document.getElementById('book-apartment-summary');
  summaryEl.innerHTML = `
    <h4>${escapeHtml(apartment.title)}</h4>
    <p>📍 ${escapeHtml(apartment.address)} &bull; 👥 Max ${apartment.max_guests} guests &bull; 💶 ${formatCurrency(apartment.price_per_night)} / night</p>
  `;

  document.getElementById('book-start-date').value = startDate || getDateOffset(1);
  document.getElementById('book-end-date').value = endDate || getDateOffset(4);

  // Trigger price calculation
  const nights = calculateNights(
    document.getElementById('book-start-date').value,
    document.getElementById('book-end-date').value
  );
  document.getElementById('book-rate').textContent = `${formatCurrency(apartment.price_per_night)} / night`;
  document.getElementById('book-duration').textContent = `${nights} night${nights === 1 ? '' : 's'}`;
  document.getElementById('book-total-price').textContent = formatCurrency(nights * apartment.price_per_night);

  // Clear guest inputs
  document.getElementById('book-guest-name').value = '';
  document.getElementById('book-guest-email').value = '';

  const errEl = document.getElementById('modal-booking-error');
  errEl.style.display = 'none';
  errEl.textContent = '';

  openModal('modal-booking');
}

/**
 * Submit Create Booking Form.
 */
async function handleCreateBooking() {
  const submitBtn = document.getElementById('btn-submit-booking');
  const errorEl = document.getElementById('modal-booking-error');
  errorEl.style.display = 'none';
  errorEl.textContent = '';

  const aptId = parseInt(document.getElementById('book-apartment-id').value, 10);
  const startDate = document.getElementById('book-start-date').value;
  const endDate = document.getElementById('book-end-date').value;
  const guestName = document.getElementById('book-guest-name').value.trim();
  const guestEmail = document.getElementById('book-guest-email').value.trim();

  if (!aptId || !startDate || !endDate || !guestName || !guestEmail) {
    errorEl.textContent = 'Please fill in all required fields.';
    errorEl.style.display = 'block';
    return;
  }

  if (endDate <= startDate) {
    errorEl.textContent = 'Check-out date must be strictly after check-in date.';
    errorEl.style.display = 'block';
    return;
  }

  submitBtn.disabled = true;
  submitBtn.textContent = 'Booking...';

  try {
    const payload = {
      apartment_id: aptId,
      start_date: startDate,
      end_date: endDate,
      guest_name: guestName,
      guest_email: guestEmail
    };

    const newBooking = await apiCall('/bookings', {
      method: 'POST',
      body: JSON.stringify(payload)
    });

    closeModal('modal-booking');
    showToast(`Reservation #${newBooking.id} confirmed! Total: ${formatCurrency(newBooking.total_price)}`, 'success', 5000);

    // Refresh search results if still on search view
    if (state.searchDates.startDate && state.searchDates.endDate) {
      performSearch();
    }

    // Also reload bookings in background
    loadBookings();

  } catch (err) {
    errorEl.textContent = err.message || 'An error occurred while creating reservation.';
    errorEl.style.display = 'block';
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Confirm Reservation';
  }
}

// -----------------------------------------------------------------------------
// Workflow 2: Apartment Catalog Management (Host View)
// -----------------------------------------------------------------------------

function setupApartmentsWorkflow() {
  const btnOpenAdd = document.getElementById('btn-open-add-apartment');
  btnOpenAdd.addEventListener('click', () => {
    document.getElementById('form-add-apartment').reset();
    document.getElementById('modal-add-apt-error').style.display = 'none';
    openModal('modal-add-apartment');
  });

  const formAdd = document.getElementById('form-add-apartment');
  formAdd.addEventListener('submit', async (e) => {
    e.preventDefault();
    await handleAddApartment();
  });

  const formEdit = document.getElementById('form-edit-apartment');
  formEdit.addEventListener('submit', async (e) => {
    e.preventDefault();
    await handleEditApartment();
  });
}

/**
 * Load all apartments from backend.
 */
async function loadApartments() {
  const grid = document.getElementById('apartments-list-grid');
  const filterSelect = document.getElementById('filter-booking-apartment');

  try {
    const apartments = await apiCall('/apartments');
    state.apartments = apartments;
    state.apartmentsMap.clear();
    apartments.forEach(apt => state.apartmentsMap.set(apt.id, apt));

    // Update filter dropdown in Bookings view
    const currentFilterVal = filterSelect.value;
    filterSelect.innerHTML = '<option value="">All Apartments</option>' +
      apartments.map(apt => `<option value="${apt.id}">#${apt.id} — ${escapeHtml(apt.title)}</option>`).join('');
    filterSelect.value = currentFilterVal;

    // Render apartments catalog
    if (apartments.length === 0) {
      grid.innerHTML = `
        <div class="empty-state">
          <span class="empty-icon">🏢</span>
          <p>No apartment listings registered yet.</p>
          <p class="text-muted">Click <strong>+ Add New Apartment</strong> to create your first listing.</p>
        </div>
      `;
      return;
    }

    grid.innerHTML = apartments.map(apt => `
      <div class="card apartment-card" data-apartment-id="${apt.id}">
        <div class="card-header">
          <h4 class="card-title">${escapeHtml(apt.title)}</h4>
          <span class="badge badge-info">ID #${apt.id}</span>
        </div>
        <div class="card-body">
          <div class="card-meta">
            <span class="meta-item"><span class="meta-icon">📍</span> ${escapeHtml(apt.address)}</span>
            <span class="meta-item"><span class="meta-icon">👥</span> Up to ${apt.max_guests} guests</span>
          </div>
          ${apt.description ? `<p class="card-description">${escapeHtml(apt.description)}</p>` : ''}
          <div class="card-pricing">
            <div class="nightly-rate">
              <span class="rate-amount">${formatCurrency(apt.price_per_night)}</span>
              <span class="rate-unit">/ night</span>
            </div>
          </div>
        </div>
        <div class="card-footer card-actions">
          <button class="btn btn-secondary btn-sm btn-edit-apt" data-apt-id="${apt.id}">
            ✏ Edit
          </button>
          <button class="btn btn-danger btn-sm btn-delete-apt" data-apt-id="${apt.id}">
            🗑 Delete
          </button>
        </div>
      </div>
    `).join('');

    // Attach actions
    grid.querySelectorAll('.btn-edit-apt').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = parseInt(btn.getAttribute('data-apt-id'), 10);
        const apt = state.apartmentsMap.get(id);
        if (apt) openEditApartmentModal(apt);
      });
    });

    grid.querySelectorAll('.btn-delete-apt').forEach(btn => {
      btn.addEventListener('click', () => {
        const id = parseInt(btn.getAttribute('data-apt-id'), 10);
        const apt = state.apartmentsMap.get(id);
        if (apt) handleDeleteApartment(apt);
      });
    });

  } catch (err) {
    grid.innerHTML = `
      <div class="alert alert-danger">
        Failed to load apartments: ${escapeHtml(err.message)}
      </div>
    `;
  }
}

/**
 * Submit Create Apartment Form.
 */
async function handleAddApartment() {
  const submitBtn = document.getElementById('btn-submit-add-apt');
  const errorEl = document.getElementById('modal-add-apt-error');
  errorEl.style.display = 'none';

  const title = document.getElementById('add-apt-title').value.trim();
  const address = document.getElementById('add-apt-address').value.trim();
  const price = parseFloat(document.getElementById('add-apt-price').value);
  const maxGuests = parseInt(document.getElementById('add-apt-guests').value, 10);
  const description = document.getElementById('add-apt-description').value.trim();

  if (!title || !address || isNaN(price) || price <= 0 || isNaN(maxGuests) || maxGuests <= 0) {
    errorEl.textContent = 'Please fill in all required fields with valid values.';
    errorEl.style.display = 'block';
    return;
  }

  submitBtn.disabled = true;
  submitBtn.textContent = 'Saving...';

  try {
    const payload = {
      title,
      address,
      price_per_night: price,
      max_guests: maxGuests,
      description: description || null
    };

    const newApt = await apiCall('/apartments', {
      method: 'POST',
      body: JSON.stringify(payload)
    });

    closeModal('modal-add-apartment');
    showToast(`Apartment "${newApt.title}" created successfully!`, 'success');
    await loadApartments();

  } catch (err) {
    errorEl.textContent = err.message || 'Failed to create apartment listing.';
    errorEl.style.display = 'block';
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Save Listing';
  }
}

/**
 * Open Edit Apartment Modal with populated values.
 * @param {object} apt
 */
function openEditApartmentModal(apt) {
  document.getElementById('edit-apt-id').value = apt.id;
  document.getElementById('edit-apt-title').value = apt.title;
  document.getElementById('edit-apt-address').value = apt.address;
  document.getElementById('edit-apt-price').value = apt.price_per_night;
  document.getElementById('edit-apt-guests').value = apt.max_guests;
  document.getElementById('edit-apt-description').value = apt.description || '';

  const errorEl = document.getElementById('modal-edit-apt-error');
  errorEl.style.display = 'none';
  errorEl.textContent = '';

  openModal('modal-edit-apartment');
}

/**
 * Submit Edit Apartment Form.
 */
async function handleEditApartment() {
  const submitBtn = document.getElementById('btn-submit-edit-apt');
  const errorEl = document.getElementById('modal-edit-apt-error');
  errorEl.style.display = 'none';

  const id = parseInt(document.getElementById('edit-apt-id').value, 10);
  const title = document.getElementById('edit-apt-title').value.trim();
  const address = document.getElementById('edit-apt-address').value.trim();
  const price = parseFloat(document.getElementById('edit-apt-price').value);
  const maxGuests = parseInt(document.getElementById('edit-apt-guests').value, 10);
  const description = document.getElementById('edit-apt-description').value.trim();

  if (!id || !title || !address || isNaN(price) || price <= 0 || isNaN(maxGuests) || maxGuests <= 0) {
    errorEl.textContent = 'Please fill in all required fields with valid values.';
    errorEl.style.display = 'block';
    return;
  }

  submitBtn.disabled = true;
  submitBtn.textContent = 'Updating...';

  try {
    const payload = {
      title,
      address,
      price_per_night: price,
      max_guests: maxGuests,
      description: description || null
    };

    const updated = await apiCall(`/apartments/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    });

    closeModal('modal-edit-apartment');
    showToast(`Apartment "${updated.title}" updated successfully!`, 'success');
    await loadApartments();

  } catch (err) {
    errorEl.textContent = err.message || 'Failed to update apartment listing.';
    errorEl.style.display = 'block';
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Update Listing';
  }
}

/**
 * Delete apartment with user confirmation and 409 conflict handling.
 * @param {object} apt
 */
async function handleDeleteApartment(apt) {
  const confirmed = window.confirm(`Are you sure you want to delete apartment "${apt.title}" (ID #${apt.id})?\n\nNote: If this apartment has active bookings, it cannot be deleted.`);
  if (!confirmed) return;

  try {
    await apiCall(`/apartments/${apt.id}`, { method: 'DELETE' });
    showToast(`Apartment "${apt.title}" deleted.`, 'success');
    await loadApartments();
  } catch (err) {
    if (err.status === 409) {
      showToast(`Cannot delete apartment: it currently has active reservations. Cancel or modify reservations first.`, 'danger', 6000);
    } else {
      showToast(`Delete failed: ${err.message}`, 'danger');
    }
  }
}

// -----------------------------------------------------------------------------
// Workflow 3: Reservations & Bookings Management
// -----------------------------------------------------------------------------

function setupBookingsWorkflow() {
  const filterSelect = document.getElementById('filter-booking-apartment');
  filterSelect.addEventListener('change', () => {
    renderBookingsTable();
  });

  const formModify = document.getElementById('form-modify-booking');
  formModify.addEventListener('submit', async (e) => {
    e.preventDefault();
    await handleModifyBooking();
  });

  // Dynamic price calculation in Modify Booking Modal
  const modStartInput = document.getElementById('modify-booking-start');
  const modEndInput = document.getElementById('modify-booking-end');
  const modAptSelect = document.getElementById('modify-booking-apartment');

  const updateModifyModalPrice = () => {
    const aptId = parseInt(modAptSelect.value, 10);
    const apt = state.apartmentsMap.get(aptId);
    const startVal = modStartInput.value;
    const endVal = modEndInput.value;
    const nights = calculateNights(startVal, endVal);

    const durEl = document.getElementById('modify-duration');
    const totEl = document.getElementById('modify-total-price');

    if (!apt) {
      durEl.textContent = '—';
      totEl.textContent = '—';
      return;
    }

    if (nights > 0) {
      durEl.textContent = `${nights} night${nights === 1 ? '' : 's'}`;
      totEl.textContent = formatCurrency(nights * apt.price_per_night);
    } else {
      durEl.textContent = 'Invalid dates';
      totEl.textContent = '—';
    }
  };

  modStartInput.addEventListener('input', updateModifyModalPrice);
  modEndInput.addEventListener('input', updateModifyModalPrice);
  modAptSelect.addEventListener('change', updateModifyModalPrice);
}

/**
 * Load all bookings from backend.
 */
async function loadBookings() {
  const tbody = document.getElementById('bookings-table-body');
  try {
    const bookings = await apiCall('/bookings');
    state.bookings = bookings;
    renderBookingsTable();
  } catch (err) {
    tbody.innerHTML = `
      <tr>
        <td colspan="8" class="text-danger text-center">
          Failed to load bookings: ${escapeHtml(err.message)}
        </td>
      </tr>
    `;
  }
}

/**
 * Render bookings table with active filter applied.
 */
function renderBookingsTable() {
  const tbody = document.getElementById('bookings-table-body');
  const filterVal = document.getElementById('filter-booking-apartment').value;
  const filtered = filterVal
    ? state.bookings.filter(b => b.apartment_id === parseInt(filterVal, 10))
    : state.bookings;

  if (filtered.length === 0) {
    tbody.innerHTML = `
      <tr>
        <td colspan="8" class="text-center text-muted" style="padding: 2.5rem 1rem;">
          No reservations found ${filterVal ? 'for this apartment' : ''}.
        </td>
      </tr>
    `;
    return;
  }

  tbody.innerHTML = filtered.map(booking => {
    const apt = state.apartmentsMap.get(booking.apartment_id);
    const aptTitle = apt ? apt.title : `Apartment #${booking.apartment_id}`;
    const nights = calculateNights(booking.start_date, booking.end_date);
    const isCancelled = booking.status === 'CANCELLED';

    const statusBadge = isCancelled
      ? '<span class="badge badge-danger">CANCELLED</span>'
      : '<span class="badge badge-success">CONFIRMED</span>';

    const actionsHtml = isCancelled
      ? '<span class="text-muted">—</span>'
      : `
        <div class="table-actions">
          <button class="btn btn-secondary btn-sm btn-modify-booking" data-booking-id="${booking.id}">
            Modify
          </button>
          <button class="btn btn-danger btn-sm btn-cancel-booking" data-booking-id="${booking.id}">
            Cancel
          </button>
        </div>
      `;

    return `
      <tr class="${isCancelled ? 'row-cancelled' : ''}">
        <td><strong>#${booking.id}</strong></td>
        <td>
          <div class="booking-apt-info">
            <span class="booking-apt-title">${escapeHtml(aptTitle)}</span>
            <small class="text-muted">ID #${booking.apartment_id}</small>
          </div>
        </td>
        <td>
          <div>${escapeHtml(booking.guest_name)}</div>
          <small class="text-muted">${escapeHtml(booking.guest_email)}</small>
        </td>
        <td>
          <span class="date-range">
            ${formatDate(booking.start_date)} &rarr; ${formatDate(booking.end_date)}
          </span>
        </td>
        <td>${nights} night${nights === 1 ? '' : 's'}</td>
        <td><strong>${formatCurrency(booking.total_price)}</strong></td>
        <td>${statusBadge}</td>
        <td>${actionsHtml}</td>
      </tr>
    `;
  }).join('');

  // Attach action listeners
  tbody.querySelectorAll('.btn-modify-booking').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = parseInt(btn.getAttribute('data-booking-id'), 10);
      const booking = state.bookings.find(b => b.id === id);
      if (booking) openModifyBookingModal(booking);
    });
  });

  tbody.querySelectorAll('.btn-cancel-booking').forEach(btn => {
    btn.addEventListener('click', () => {
      const id = parseInt(btn.getAttribute('data-booking-id'), 10);
      handleCancelBooking(id);
    });
  });
}

/**
 * Open Modify Booking Modal.
 * @param {object} booking
 */
function openModifyBookingModal(booking) {
  state.currentModifyBooking = booking;

  document.getElementById('modify-booking-id').value = booking.id;

  // Populate apartment selector
  const aptSelect = document.getElementById('modify-booking-apartment');
  aptSelect.innerHTML = state.apartments.map(apt => `
    <option value="${apt.id}" ${apt.id === booking.apartment_id ? 'selected' : ''}>
      #${apt.id} — ${escapeHtml(apt.title)} (${formatCurrency(apt.price_per_night)}/night)
    </option>
  `).join('');

  document.getElementById('modify-booking-start').value = booking.start_date;
  document.getElementById('modify-booking-end').value = booking.end_date;
  document.getElementById('modify-booking-name').value = booking.guest_name;
  document.getElementById('modify-booking-email').value = booking.guest_email;

  const nights = calculateNights(booking.start_date, booking.end_date);
  document.getElementById('modify-duration').textContent = `${nights} night${nights === 1 ? '' : 's'}`;
  document.getElementById('modify-total-price').textContent = formatCurrency(booking.total_price);

  const errorEl = document.getElementById('modal-modify-booking-error');
  errorEl.style.display = 'none';
  errorEl.textContent = '';

  openModal('modal-modify-booking');
}

/**
 * Submit Modify Booking Form.
 */
async function handleModifyBooking() {
  const submitBtn = document.getElementById('btn-submit-modify-booking');
  const errorEl = document.getElementById('modal-modify-booking-error');
  errorEl.style.display = 'none';

  const id = parseInt(document.getElementById('modify-booking-id').value, 10);
  const aptId = parseInt(document.getElementById('modify-booking-apartment').value, 10);
  const startDate = document.getElementById('modify-booking-start').value;
  const endDate = document.getElementById('modify-booking-end').value;
  const guestName = document.getElementById('modify-booking-name').value.trim();
  const guestEmail = document.getElementById('modify-booking-email').value.trim();

  if (!id || !aptId || !startDate || !endDate || !guestName || !guestEmail) {
    errorEl.textContent = 'Please fill in all required fields.';
    errorEl.style.display = 'block';
    return;
  }

  if (endDate <= startDate) {
    errorEl.textContent = 'Check-out date must be strictly after check-in date.';
    errorEl.style.display = 'block';
    return;
  }

  submitBtn.disabled = true;
  submitBtn.textContent = 'Saving...';

  try {
    const payload = {
      apartment_id: aptId,
      start_date: startDate,
      end_date: endDate,
      guest_name: guestName,
      guest_email: guestEmail
    };

    const updated = await apiCall(`/bookings/${id}`, {
      method: 'PUT',
      body: JSON.stringify(payload)
    });

    closeModal('modal-modify-booking');
    showToast(`Reservation #${updated.id} updated! Total: ${formatCurrency(updated.total_price)}`, 'success');
    await loadBookings();

  } catch (err) {
    errorEl.textContent = err.message || 'Failed to modify reservation.';
    errorEl.style.display = 'block';
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = 'Save Changes';
  }
}

/**
 * Cancel a booking with confirmation.
 * @param {number} bookingId
 */
async function handleCancelBooking(bookingId) {
  const confirmed = window.confirm(`Are you sure you want to cancel Reservation #${bookingId}?\n\nThis will release the dates so other guests can book.`);
  if (!confirmed) return;

  try {
    const cancelled = await apiCall(`/bookings/${bookingId}/cancel`, {
      method: 'POST'
    });

    showToast(`Reservation #${cancelled.id} cancelled. Dates released!`, 'success');
    await loadBookings();

    // If search view was active with dates, refresh search
    if (state.searchDates.startDate && state.searchDates.endDate) {
      performSearch();
    }
  } catch (err) {
    showToast(`Failed to cancel reservation: ${err.message}`, 'danger');
  }
}

// -----------------------------------------------------------------------------
// App Initialization
// -----------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', async () => {
  setupModalEvents();
  setupTabNavigation();
  setupSearchWorkflow();
  setupApartmentsWorkflow();
  setupBookingsWorkflow();

  // Initial data load: apartments catalog & pre-run default search
  try {
    await loadApartments();
    await performSearch();
  } catch (err) {
    console.error('Initial load error:', err);
  }
});
