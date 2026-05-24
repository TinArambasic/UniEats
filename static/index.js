  const API = '';
  const FALLBACK_IMAGE = '/static/fallback-food.svg';
  const HERO_FOOD_FALLBACK = '/static/hero-food.svg';
  let token = localStorage.getItem('token') || '';
  let currentUser = null;
  let menuItems = [];
  let cart = {};
  let selectedCategory = '';
  let selectedCategoryToken = '';
  let adminAllItems = [];
  let ownerAdmins = [];
  let orgUsers = [];
  let adminEditId = null;
  let loginMode = 'student';
  let adminOriginalImageUrl = FALLBACK_IMAGE;
  let selectedOrganizationId = null;
  let organizationCatalog = [];
  let organizationModalTab = 'all';
  let organizationSearchTerm = '';
  let organizationCityFilters = [];
  let organizationCityDropdownOpen = false;
  let profileAvatarPendingFile = null;
  let activeStaffOrganizationId = null;
  let activeOrganizationEditId = null;
  let activeOrganizationHours = [];
  let isspEnabled = false; // ISSP service availability flag
  let isspLinkMode = 'manual';
  let isspProfileData = null;
  let activeView = 'home';
  let menuChipFilter = 'all';
  let favoriteMenuItems = {};
  let mealRatings = {};
  let userMealRatings = {};
  let pendingRatingValue = 5;
  let selectedRatingItemId = null;
  let personalOrders = [];
  let globalOrders = [];
  let popularItemStats = [];
  let recommendedCarouselIndex = 0;
  let experienceCarouselItems = [];
  let experienceTouchStartX = null;

  const CATEGORY_PRIORITY_ORDER = [
    'Juhe',
    'Glavno jelo',
    'Prilog',
    'Salata',
    'Desert',
    'Mliječni proizvodi',
    'Vege jela',
    'Brza jela',
    'Variva',
    'Pića',
    'Napitci',
  ];
  const CATEGORY_PRIORITY_INDEX = CATEGORY_PRIORITY_ORDER.reduce((acc, label, index) => {
    acc[normalizeCategoryToken(label)] = index;
    return acc;
  }, {});

  //  HELPERS 

  function authHeaders() {
    return { 'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json' };
  }

  const EUR_FORMATTER = new Intl.NumberFormat('hr-HR', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

  function fmt(n) {
    const value = Number(n);
    const safe = Number.isFinite(value) ? value : 0;
    try {
      return EUR_FORMATTER.format(safe);
    } catch {
      return safe.toFixed(2).replace('.', ',') + ' €';
    }
  }

  function normalizeCategoryToken(value) {
    return String(value || '')
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .trim();
  }

  function userStorageKey(key) {
    const userId = currentUser && currentUser.id ? String(currentUser.id) : 'guest';
    return `unieats_${key}_${userId}`;
  }

  function getISSPStorageKey() {
    return userStorageKey('issp_profile');
  }

  function getSelectedOrganizationStorageKey() {
    return userStorageKey('selected_org_id');
  }

  function persistSelectedOrganizationId() {
    if (!currentUser) return;
    const key = getSelectedOrganizationStorageKey();
    if (!selectedOrganizationId) {
      localStorage.removeItem(key);
      return;
    }
    localStorage.setItem(key, String(selectedOrganizationId));
  }

  function loadStoredSelectedOrganizationId() {
    if (!currentUser) return null;
    try {
      const raw = localStorage.getItem(getSelectedOrganizationStorageKey());
      const parsed = Number(raw);
      return Number.isFinite(parsed) && parsed > 0 ? parsed : null;
    } catch {
      return null;
    }
  }

  function loadStoredISSPProfile() {
    try {
      const raw = localStorage.getItem(getISSPStorageKey());
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === 'object' ? parsed : null;
    } catch {
      return null;
    }
  }

  function saveISSPProfile(profile) {
    if (!currentUser || !profile || typeof profile !== 'object') return;
    try {
      localStorage.setItem(getISSPStorageKey(), JSON.stringify(profile));
    } catch {
      // ignore storage quota issues in UI layer
    }
  }

  function clearISSPProfileStorage() {
    if (!currentUser) return;
    localStorage.removeItem(getISSPStorageKey());
  }

  function normalizeISSPPayload(data) {
    if (!data || typeof data !== 'object') return null;
    const firstName = String(data.first_name || '').trim();
    const lastName = String(data.last_name || '').trim();
    const fallbackFullName = String(data.full_name || '').trim();
    const fullName = [firstName, lastName].filter(Boolean).join(' ') || fallbackFullName || null;
    const profileImageUrl = String(data.profile_image_url || '').trim() || null;
    const faculty = String(data.faculty || '').trim() || null;
    const cardNumber = String(data.card_number || data.student_card_number || '').trim() || null;
    const esi = String(data.esi || data.student_esi || '').trim() || null;
    const subsidy = data.subsidy_remaining != null ? Number(data.subsidy_remaining) : null;
    return {
      full_name: fullName,
      first_name: firstName || null,
      last_name: lastName || null,
      faculty,
      profile_image_url: profileImageUrl,
      subsidy_remaining: Number.isFinite(subsidy) ? subsidy : null,
      card_number: cardNumber,
      esi,
      source: String(data.source || 'issp'),
    };
  }

  function applyISSPDataToCurrentUser(data, options = {}) {
    const normalized = normalizeISSPPayload(data);
    if (!normalized || !currentUser) return null;
    const persist = options.persist !== false;
    isspProfileData = normalized;
    if (persist) saveISSPProfile(normalized);

    if (normalized.first_name) currentUser.first_name = normalized.first_name;
    if (normalized.last_name) currentUser.last_name = normalized.last_name;
    if (normalized.card_number) currentUser.student_card_number = normalized.card_number;
    if (normalized.esi) currentUser.student_esi = normalized.esi;
    if (normalized.subsidy_remaining != null) currentUser.subsidy_remaining = normalized.subsidy_remaining;
    if (normalized.profile_image_url) currentUser.profile_image_url = normalized.profile_image_url;
    if (currentUser.subsidy_remaining != null) {
      const navSubsidy = document.getElementById('nav-subsidy');
      if (navSubsidy) {
        navSubsidy.textContent = 'Subvencija: ' + fmt(Number(currentUser.subsidy_remaining));
        navSubsidy.style.display = '';
      }
    }
    syncAvatarUIFromCurrentUser();
    return normalized;
  }

  function hydrateISSPProfileFromStorage() {
    isspProfileData = loadStoredISSPProfile();
    if (isspProfileData) {
      applyISSPDataToCurrentUser(isspProfileData, { persist: false });
    }
  }

  function fmtDateShort(dateInput) {
    const dt = new Date(dateInput);
    if (Number.isNaN(dt.getTime())) return '-';
    return dt.toLocaleDateString('hr-HR', { day: '2-digit', month: 'long', year: 'numeric' });
  }

  function getItemById(itemId) {
    return menuItems.find(item => Number(item.id) === Number(itemId)) || null;
  }

  function showToast(msg, duration = 2800) {
    const t = document.getElementById('toast');
    t.textContent = msg;
    t.classList.add('show');
    setTimeout(() => t.classList.remove('show'), duration);
  }

  function minPickupTime() {
    const d = new Date();
    d.setMinutes(d.getMinutes() + 30);
    return d.toISOString().slice(0, 16);
  }

  function parseOptFloat(val) {
    const v = parseFloat(val);
    return isNaN(v) ? null : v;
  }

  function itemImageSrc(item) {
    return item && item.image_url ? item.image_url : FALLBACK_IMAGE;
  }

  function normalizeRole(role) {
    const value = String(role || '').toLowerCase().trim();
    if (value === 'owner' || value === 'superadmin' || value === 'administrator') return 'owner';
    if (value === 'admin' || value === 'staff' || value === 'employee' || value === 'djelatnik') return 'admin';
    return 'student';
  }

  function isStaffRole() {
    const role = normalizeRole(currentUser && currentUser.role);
    return role === 'admin' || role === 'owner';
  }

  function isOwnerRole() {
    return normalizeRole(currentUser && currentUser.role) === 'owner';
  }

  function roleLabel(role) {
    const normalized = normalizeRole(role);
    if (normalized === 'owner') return 'Admin organizacije';
    if (normalized === 'admin') return 'Djelatnik';
    return 'Student';
  }

  function roleBadgeClass(role) {
    const normalized = normalizeRole(role);
    if (normalized === 'owner') return 'owner';
    if (normalized === 'admin') return 'staff';
    return 'student';
  }

  function getOrganizationName(user) {
    if (!user) return '-';
    if (user.organization && user.organization.name) return user.organization.name;
    if (user.organization_name) return user.organization_name;
    const orgId = Number(user.organization_id);
    if (orgId) {
      const orgFromCatalog = getOrganizationById(orgId);
      if (orgFromCatalog && orgFromCatalog.name) return orgFromCatalog.name;
      const staffOrgs = currentUser && Array.isArray(currentUser.organizations)
        ? currentUser.organizations
        : [];
      const orgFromStaffList = staffOrgs.find(org => Number(org.id) === orgId);
      if (orgFromStaffList && orgFromStaffList.name) return orgFromStaffList.name;
      return `Organizacija #${orgId}`;
    }
    return '-';
  }

  function getStaffOrganizations() {
    if (!isStaffRole() || !currentUser) return [];
    const list = Array.isArray(currentUser.organizations) ? [...currentUser.organizations] : [];
    if (list.length > 0) return list;
    if (currentUser.organization && currentUser.organization.id) {
      return [currentUser.organization];
    }
    if (currentUser.organization_id) {
      return [{ id: currentUser.organization_id, name: getOrganizationName(currentUser) }];
    }
    return [];
  }

  function resolvePreferredStaffOrganizationId(preferredId = null) {
    const organizations = getStaffOrganizations();
    const availableIds = organizations
      .map(org => Number(org.id))
      .filter(id => Number.isFinite(id) && id > 0);
    const preferred = Number(preferredId);
    if (Number.isFinite(preferred) && preferred > 0 && availableIds.includes(preferred)) {
      return preferred;
    }
    const primary = Number(currentUser && currentUser.organization_id);
    if (Number.isFinite(primary) && primary > 0 && (availableIds.length === 0 || availableIds.includes(primary))) {
      return primary;
    }
    return availableIds.length > 0 ? availableIds[0] : null;
  }

  function getActiveStaffOrganizationId() {
    if (!isStaffRole()) return null;
    if (!activeStaffOrganizationId) {
      activeStaffOrganizationId = resolvePreferredStaffOrganizationId();
    }
    return activeStaffOrganizationId;
  }

  function syncStaffOrganizationFromUser(preferredId = null) {
    if (!isStaffRole()) {
      activeStaffOrganizationId = null;
      return null;
    }
    activeStaffOrganizationId = resolvePreferredStaffOrganizationId(preferredId);
    if (currentUser && activeStaffOrganizationId) {
      currentUser.organization_id = activeStaffOrganizationId;
      const staffOrg = getStaffOrganizations().find(org => Number(org.id) === Number(activeStaffOrganizationId));
      if (staffOrg) {
        currentUser.organization = { ...(currentUser.organization || {}), ...staffOrg };
      }
    }
    return activeStaffOrganizationId;
  }

  async function setActiveStaffOrganization(nextOrganizationId, options = {}) {
    const reloadMenu = !!options.reloadMenu;
    const reloadUsers = !!options.reloadUsers;
    if (!isStaffRole()) return;
    const resolved = resolvePreferredStaffOrganizationId(nextOrganizationId);
    if (!resolved) return;
    const changed = Number(activeStaffOrganizationId) !== Number(resolved);
    activeStaffOrganizationId = resolved;
    selectedOrganizationId = resolved;
    if (!currentUser) return;
    currentUser.organization_id = resolved;
    const staffOrg = getStaffOrganizations().find(org => Number(org.id) === Number(resolved));
    if (staffOrg) {
      currentUser.organization = { ...(currentUser.organization || {}), ...staffOrg };
    }
    renderStaffOrganizationSelector();
    if (!changed) return;
    if (reloadMenu) {
      await loadMenu();
    }
    if (reloadUsers && document.getElementById('users-section').style.display !== 'none') {
      await loadOrganizationUsers();
    }
    if (document.getElementById('profile-section').style.display !== 'none') {
      await renderProfilePage();
    }
    await loadDashboardOrders();
  }

  function setRoleTheme(theme) {
    document.body.dataset.roleTheme = theme;
    const indicator = document.getElementById('role-indicator');
    if (indicator) {
      indicator.classList.remove('student', 'staff', 'owner');
      indicator.classList.add(theme);
    }
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function userDisplayName(user) {
    if (!user) return '-';
    const full = [user.first_name || '', user.last_name || ''].join(' ').trim();
    return full || user.email || '-';
  }

  function loadUserUiState() {
    try {
      favoriteMenuItems = JSON.parse(localStorage.getItem(userStorageKey('favorite_items')) || '{}') || {};
    } catch {
      favoriteMenuItems = {};
    }
    selectedOrganizationId = loadStoredSelectedOrganizationId();
    mealRatings = {};
    userMealRatings = {};
  }

  function persistFavoriteItems() {
    localStorage.setItem(userStorageKey('favorite_items'), JSON.stringify(favoriteMenuItems));
  }


  async function loadRatingsData() {
    mealRatings = {};
    userMealRatings = {};

    try {
      const summaryRes = await fetch('/ratings/summary', { headers: authHeaders() });
      if (summaryRes.ok) {
        const summaryRows = await summaryRes.json();
        summaryRows.forEach(row => {
          const itemId = String(row.menu_item_id);
          const count = Number(row.rating_count || 0);
          const avg = Number(row.average_rating || 0);
          mealRatings[itemId] = {
            total: avg * count,
            count,
          };
        });
      }
    } catch {}

    try {
      const myRes = await fetch('/ratings/my', { headers: authHeaders() });
      if (myRes.ok) {
        const rows = await myRes.json();
        rows.forEach(row => {
          userMealRatings[String(row.menu_item_id)] = Number(row.rating || 0);
        });
      }
    } catch {}
  }

  function isItemFavorite(itemId) {
    return !!favoriteMenuItems[String(itemId)];
  }

  function toggleItemFavorite(itemId, event) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }
    const key = String(itemId);
    if (favoriteMenuItems[key]) {
      delete favoriteMenuItems[key];
    } else {
      favoriteMenuItems[key] = true;
    }
    persistFavoriteItems();
    renderMenu();
    renderFavorites();
    renderRecommendedPanel();
    renderPopularPanel();
  }

  function getItemRatingMeta(itemId) {
    const row = mealRatings[String(itemId)];
    const count = row ? Number(row.count || 0) : 0;
    if (count <= 0) {
      return { average: 0, count: 0 };
    }
    return {
      average: Number(row.total || 0) / count,
      count,
    };
  }

  function setTodayMenuDate() {
    const dateEl = document.getElementById('today-menu-date');
    if (!dateEl) return;
    dateEl.textContent = fmtDateShort(new Date());
  }

  function formatRoleForSidebar(role) {
    const normalized = normalizeRole(role);
    if (normalized === 'owner') return 'Admin';
    if (normalized === 'admin') return 'Djelatnik';
    return 'Student';
  }

  function setNavItemVisibility(id, visible) {
    const el = document.getElementById(id);
    if (!el) return;
    el.style.display = visible ? 'flex' : 'none';
  }

  function canAccessTab(tab) {
    const value = String(tab || '').toLowerCase();
    if (value === 'admin') return isStaffRole();
    if (value === 'users') return isOwnerRole();
    return ['home', 'menu', 'orders', 'favorites', 'profile'].includes(value);
  }

  function normalizeTabForCurrentUser(tab) {
    const value = String(tab || '').toLowerCase().trim();
    if (canAccessTab(value)) return value;
    return 'home';
  }

  function setTabLinkState(id, active) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.toggle('active', active);
    if (active) {
      el.setAttribute('aria-current', 'page');
    } else {
      el.removeAttribute('aria-current');
    }
  }

  function applyRoleBasedNavigationVisibility() {
    const authenticated = !!currentUser;
    setNavItemVisibility('tab-home', authenticated);
    setNavItemVisibility('tab-menu', authenticated);
    setNavItemVisibility('tab-orders', authenticated);
    setNavItemVisibility('tab-favorites', authenticated);
    setNavItemVisibility('tab-admin', authenticated && isStaffRole());
    setNavItemVisibility('tab-users', authenticated && isOwnerRole());
    setNavItemVisibility('tab-profile', authenticated);
    if (authenticated) {
      activeView = normalizeTabForCurrentUser(activeView);
    }
  }

  function readTabFromHash() {
    if (typeof window === 'undefined') return 'home';
    const hash = String(window.location.hash || '').replace(/^#/, '');
    return normalizeTabForCurrentUser(hash || 'home');
  }

  function writeTabToHash(tab) {
    if (typeof window === 'undefined') return;
    const nextHash = `#${tab}`;
    if (window.location.hash !== nextHash) {
      window.history.replaceState(null, '', nextHash);
    }
  }

  function handleSidebarNavigation(event, tab) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }
    void showTab(tab);
  }

  function isMobileLayout() {
    return typeof window !== 'undefined' && window.matchMedia('(max-width: 980px)').matches;
  }

  function openMobileSidebar() {
    if (!isMobileLayout()) return;
    document.body.classList.add('mobile-sidebar-open');
  }

  function closeMobileSidebar() {
    document.body.classList.remove('mobile-sidebar-open');
  }

  function toggleMobileSidebar() {
    if (!isMobileLayout()) return;
    document.body.classList.toggle('mobile-sidebar-open');
  }

  if (typeof window !== 'undefined') {
    window.addEventListener('hashchange', () => {
      if (!currentUser) return;
      const targetTab = readTabFromHash();
      if (targetTab !== activeView) {
        void showTab(targetTab, { updateHash: false });
      }
    });
    window.addEventListener('resize', () => {
      if (!isMobileLayout()) {
        closeMobileSidebar();
      }
    });
  }

  function getBackendAvatarUrl(user) {
    if (!user || typeof user !== 'object') return '';
    const value = [user.avatar_url, user.profile_image_url, user.image_url]
      .find(candidate => typeof candidate === 'string' && candidate.trim());
    return value ? value.trim() : '';
  }

  function applyAvatarToUI(imageUrl) {
    const hasImage = !!imageUrl;
    [
      ['nav-profile-btn', 'nav-avatar-img'],
      ['profile-avatar', 'profile-avatar-img'],
      ['sidebar-profile-avatar', 'sidebar-profile-avatar-img'],
    ].forEach(([wrapId, imgId]) => {
      const wrap = document.getElementById(wrapId);
      const img = document.getElementById(imgId);
      if (wrap && img) {
        img.src = hasImage ? imageUrl : '';
        wrap.classList.toggle('has-image', hasImage);
      }
    });
  }

  function syncSidebarProfileCard() {
    const nameEl = document.getElementById('sidebar-profile-name');
    const roleEl = document.getElementById('sidebar-profile-role');
    if (nameEl) nameEl.textContent = userDisplayName(currentUser);
    if (roleEl) roleEl.textContent = formatRoleForSidebar(currentUser && currentUser.role);
  }

  function syncAvatarUIFromCurrentUser() {
    applyAvatarToUI(getBackendAvatarUrl(currentUser));
    syncSidebarProfileCard();
  }

  async function onProfileAvatarSelected(event) {
    const input = event && event.target;
    const file = input && input.files ? input.files[0] : null;
    if (!file) return;
    const allowed = ['image/jpeg', 'image/png', 'image/webp'];
    if (!allowed.includes(file.type)) {
      showToast('Avatar mora biti JPEG, PNG ili WEBP.');
      input.value = '';
      return;
    }
    if (file.size > 3 * 1024 * 1024) {
      showToast('Maksimalna veličina avatar slike je 3MB.');
      input.value = '';
      return;
    }
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch('/auth/me/avatar', {
      method: 'POST',
      headers: { 'Authorization': 'Bearer ' + token },
      body: formData,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      showToast(err.detail || 'Neuspjelo spremanje avatara.');
      input.value = '';
      return;
    }
    currentUser = await res.json();
    syncAvatarUIFromCurrentUser();
    input.value = '';
    showToast('Avatar je uspješno ažuriran.');
    await renderProfilePage();
  }

  function openProfilePage() {
    if (!currentUser) return;
    showTab('profile');
  }

  async function ensureProfileDataLoaded() {
    if (isStaffRole() && orgUsers.length === 0) {
      const params = new URLSearchParams();
      const activeOrgId = getActiveStaffOrganizationId();
      if (activeOrgId) params.set('organization_id', String(activeOrgId));
      const url = params.toString() ? `/auth/users?${params.toString()}` : '/auth/users';
      const usersRes = await fetch(url, { headers: authHeaders() });
      if (usersRes.ok) orgUsers = await usersRes.json();
    }
    if (isOwnerRole() && ownerAdmins.length === 0) {
      const adminsRes = await fetch('/auth/admins', { headers: authHeaders() });
      if (adminsRes.ok) ownerAdmins = await adminsRes.json();
    }
  }

  function buildOrganizationBuckets(users) {
    const byOrg = {};
    users.forEach(user => {
      const orgName = getOrganizationName(user);
      if (!byOrg[orgName]) byOrg[orgName] = [];
      byOrg[orgName].push(user);
    });
    return Object.entries(byOrg).sort(([a], [b]) => a.localeCompare(b));
  }

  function addWorkspaceOrganization() {
    showToast('Dodavanje organizacije nije dostupno bez backend podrške.');
    return;
    /*
    const input = document.getElementById('profile-new-org-input');
    if (!input) return;
    const name = normalizeOrganizationName(input.value);
    if (!name) {
      showToast('Unesite naziv organizacije.');
      return;
    }
    if (ownerWorkspaceOrganizations.includes(name)) {
      showToast('Organizacija ve! postoji u UI listi.');
      return;
    }
    ownerWorkspaceOrganizations.push(name);
    ownerWorkspaceOrganizations.sort((a, b) => a.localeCompare(b));
    input.value = '';
    renderProfilePage();
    showToast('Organizacija dodana u UI radni prostor.');
    */
  }

  function moveStaffToOrganization(adminId) {
    void adminId;
    showToast('Premještanje djelatnika nije dostupno bez backend podrške.');
  }


  const WEEK_DAYS = [
    { day: 0, label: 'Ponedjeljak' },
    { day: 1, label: 'Utorak' },
    { day: 2, label: 'Srijeda' },
    { day: 3, label: 'Cetvrtak' },
    { day: 4, label: 'Petak' },
    { day: 5, label: 'Subota' },
    { day: 6, label: 'Nedjelja' },
  ];

  function isStudentRole() {
    return normalizeRole(currentUser && currentUser.role) === 'student';
  }

  function jsDayToBackendDay(jsDay) {
    return (jsDay + 6) % 7;
  }

  function parseHHMM(value) {
    if (!value || !value.includes(':')) return null;
    const [hRaw, mRaw] = value.split(':');
    const h = Number(hRaw);
    const m = Number(mRaw);
    if (Number.isNaN(h) || Number.isNaN(m)) return null;
    return { h, m };
  }

  function getOrganizationById(organizationId) {
    return organizationCatalog.find(org => Number(org.id) === Number(organizationId)) || null;
  }

  function getSelectedOrganization() {
    if (!selectedOrganizationId) return null;
    return getOrganizationById(selectedOrganizationId);
  }

  function computeOrganizationOrderability(organization) {
    if (!organization) {
      return { canOrderNow: false, reason: 'Odaberite restoran prije narudžbe.' };
    }
    if (typeof organization.can_order_now === 'boolean') {
      return {
        canOrderNow: organization.can_order_now,
        reason: organization.can_order_now ? '' : (organization.order_block_reason || 'Narudžba trenutno nije moguća.'),
      };
    }
    const workingHours = Array.isArray(organization.working_hours) ? organization.working_hours : [];
    const today = workingHours.find(row => Number(row.day_of_week) === jsDayToBackendDay(new Date().getDay()));
    if (!today) return { canOrderNow: false, reason: 'Za danas nije definirano radno vrijeme restorana.' };
    if (today.is_closed) return { canOrderNow: false, reason: 'Restoran je danas zatvoren.' };

    const openParsed = parseHHMM(today.open_time);
    const closeParsed = parseHHMM(today.close_time);
    if (!openParsed || !closeParsed) {
      return { canOrderNow: false, reason: 'Restoran danas nema kompletno radno vrijeme.' };
    }
    const now = new Date();
    const openDate = new Date(now);
    openDate.setHours(openParsed.h, openParsed.m, 0, 0);
    const closeDate = new Date(now);
    closeDate.setHours(closeParsed.h, closeParsed.m, 0, 0);
    const cutoff = new Date(closeDate.getTime() - (30 * 60 * 1000));
    if (now < openDate) return { canOrderNow: false, reason: `Restoran se otvara u ${today.open_time}.` };
    if (now >= closeDate) return { canOrderNow: false, reason: `Restoran je zatvoren (do ${today.close_time}).` };
    if (now > cutoff) {
      return { canOrderNow: false, reason: `Narudžba je moguća najkasnije 30 minuta prije zatvaranja (${today.close_time}).` };
    }
    return { canOrderNow: true, reason: '' };
  }

  function getOrderBlockReason() {
    if (!currentUser) return '';
    if (isStudentRole() && !selectedOrganizationId) {
      return 'Odaberite restoran prije dodavanja i slanja narudžbe.';
    }
    const selected = getSelectedOrganization();
    if (!selected) return '';
    const status = computeOrganizationOrderability(selected);
    return status.canOrderNow ? '' : (status.reason || 'Narudžba trenutno nije moguća.');
  }

  function refreshOrderGateUi() {
    const summaryEl = document.getElementById('cart-org-summary');
    const reasonEl = document.getElementById('cart-order-rule-msg');
    const orderBtn = document.getElementById('place-order-btn');
    if (!summaryEl || !reasonEl || !orderBtn) return;

    const selected = getSelectedOrganization();
    if (selected) {
      summaryEl.innerHTML = `Odabrani restoran: <strong>${escapeHtml(selected.name)}</strong>${selected.city ? `, ${escapeHtml(selected.city)}` : ''}${isStudentRole() ? ` <button type="button" class="btn btn-ghost btn-sm" style="margin-left:.45rem" onclick="openOrganizationPickerModal()">Promijeni</button>` : ''}`;
    } else if (isStudentRole()) {
      summaryEl.innerHTML = `Restoran nije odabran. <button type="button" class="btn btn-ghost btn-sm" style="margin-left:.45rem" onclick="openOrganizationPickerModal()">Odaberi restoran</button>`;
    } else {
      summaryEl.innerHTML = '';
    }

    const reason = getOrderBlockReason();
    reasonEl.style.display = reason ? '' : 'none';
    reasonEl.textContent = reason || '';
    orderBtn.disabled = !!reason;
    orderBtn.textContent = isStudentRole() ? 'Naruči odmah' : 'Naruči';
  }

  function refreshStudentSelectorUi() {
    const gate = document.getElementById('student-org-gate');
    if (!gate) return;
    const nameEl = document.getElementById('student-selected-org-name');
    const subEl = document.getElementById('student-selected-org-sub');
    const clearBtn = document.getElementById('student-clear-org-btn');
    const pickBtn = document.getElementById('student-pick-org-btn');

    gate.style.display = '';

    if (!isStudentRole()) {
      const activeOrg = getOrganizationById(getActiveStaffOrganizationId()) || null;
      nameEl.textContent = activeOrg ? activeOrg.name : getOrganizationName(currentUser);
      subEl.textContent = activeOrg
        ? 'Aktivna organizacija za upravljanje jelovnikom i narudžbama.'
        : 'Organizaciju možete urediti kroz profil.';
      if (clearBtn) clearBtn.style.display = 'none';
      if (pickBtn) {
        pickBtn.textContent = 'Uredi organizaciju';
        pickBtn.onclick = () => openOrganizationEditModal(getActiveStaffOrganizationId());
      }
      refreshOrderGateUi();
      return;
    }

    if (pickBtn) {
      pickBtn.textContent = 'Odaberi restoran';
      pickBtn.onclick = () => openOrganizationPickerModal();
    }

    const selected = getSelectedOrganization();
    if (!selected) {
      nameEl.textContent = 'Nije odabran restoran';
      subEl.textContent = 'Odaberite restoran prije dodavanja artikala u košaricu.';
      if (clearBtn) clearBtn.style.display = 'none';
      refreshOrderGateUi();
      return;
    }
    const status = computeOrganizationOrderability(selected);
    nameEl.textContent = selected.name;
    subEl.textContent = status.canOrderNow ? 'Restoran je spreman za narudžbe.' : (status.reason || 'Narudžba trenutno nije moguća.');
    if (clearBtn) clearBtn.style.display = '';
    refreshOrderGateUi();
  }

  async function loadOrganizationCatalog() {
    const res = await fetch('/organizations', { headers: authHeaders() });
    if (!res.ok) {
      organizationCatalog = [];
      return;
    }
    organizationCatalog = await res.json();
    if (
      selectedOrganizationId &&
      !organizationCatalog.some(org => Number(org.id) === Number(selectedOrganizationId))
    ) {
      selectedOrganizationId = null;
      persistSelectedOrganizationId();
    }
  }

  function resolveDefaultStudentOrganizationId() {
    if (!Array.isArray(organizationCatalog) || organizationCatalog.length === 0) return null;
    const active = organizationCatalog.filter(org => org && org.is_active !== false);
    const source = active.length > 0 ? active : organizationCatalog;
    const stored = Number(selectedOrganizationId);
    if (Number.isFinite(stored) && stored > 0 && source.some(org => Number(org.id) === stored)) {
      return stored;
    }
    const userOrgId = Number(currentUser && currentUser.organization_id);
    if (Number.isFinite(userOrgId) && userOrgId > 0 && source.some(org => Number(org.id) === userOrgId)) {
      return userOrgId;
    }
    const preferred = source.find(org => org.is_favorite && org.can_order_now !== false) ||
      source.find(org => org.can_order_now !== false) ||
      source[0];
    return preferred ? Number(preferred.id) : null;
  }

  async function ensureStudentOrganizationSelection() {
    if (!isStudentRole() || selectedOrganizationId) return;
    if (!Array.isArray(organizationCatalog) || organizationCatalog.length === 0) {
      await loadOrganizationCatalog();
    }
    const resolved = resolveDefaultStudentOrganizationId();
    if (resolved) {
      selectedOrganizationId = resolved;
      persistSelectedOrganizationId();
    }
  }

  function getOrganizationModalItems() {
    const base = organizationModalTab === 'favorites'
      ? organizationCatalog.filter(org => org.is_favorite)
      : organizationCatalog;
    const q = organizationSearchTerm.trim().toLowerCase();
    const selectedCities = organizationCityFilters.map(city => city.toLowerCase());
    return base.filter(org => {
      if (selectedCities.length > 0) {
        const city = (org.city || '').toLowerCase();
        if (!selectedCities.includes(city)) return false;
      }
      if (!q) return true;
      const text = `${org.name || ''} ${org.city || ''} ${org.address || ''}`.toLowerCase();
      return text.includes(q);
    });
  }

  function renderOrganizationCityFilter() {
    const cityMenu = document.getElementById('org-city-filter-menu');
    const cityLabel = document.getElementById('org-city-filter-label');
    const cityCount = document.getElementById('org-city-filter-count');
    const selectedWrap = document.getElementById('org-city-selected');
    if (!cityMenu || !cityLabel || !cityCount || !selectedWrap) return;

    const cities = [...new Set(organizationCatalog.map(org => (org.city || '').trim()).filter(Boolean))]
      .sort((a, b) => a.localeCompare(b));
    organizationCityFilters = organizationCityFilters.filter(city =>
      cities.some(existing => existing.toLowerCase() === city.toLowerCase())
    );
    const selectedLower = new Set(organizationCityFilters.map(city => city.toLowerCase()));

    cityMenu.innerHTML = cities.length === 0
      ? '<div class="city-filter-option">Nema gradova</div>'
      : cities.map(city => {
          const active = selectedLower.has(city.toLowerCase());
          const encoded = encodeURIComponent(city);
          return `
            <label class="city-filter-option ${active ? 'active' : ''}" onclick="toggleOrganizationCityFilterOption(event, '${encoded}')">
              <input type="checkbox" ${active ? 'checked' : ''} />
              <span>${escapeHtml(city)}</span>
            </label>
          `;
        }).join('');

    if (organizationCityFilters.length === 0) {
      cityLabel.textContent = 'Svi gradovi';
      cityCount.style.display = 'none';
      selectedWrap.style.display = 'none';
      selectedWrap.innerHTML = '';
      return;
    }

    cityLabel.textContent = `Gradovi (${organizationCityFilters.length})`;
    cityCount.style.display = '';
    cityCount.textContent = String(organizationCityFilters.length);
    selectedWrap.style.display = '';
    selectedWrap.innerHTML = organizationCityFilters.map(city => `
      <span class="city-chip">
        ${escapeHtml(city)}
        <button type="button" class="city-chip-remove" onclick="removeOrganizationCityFilter(event, '${encodeURIComponent(city)}')" aria-label="Ukloni grad ${escapeHtml(city)}">&times;</button>
      </span>
    `).join('');
  }

  function closeOrganizationCityDropdown() {
    organizationCityDropdownOpen = false;
    const cityMenu = document.getElementById('org-city-filter-menu');
    if (cityMenu) cityMenu.classList.remove('show');
  }

  function toggleOrganizationCityDropdown(event) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }
    organizationCityDropdownOpen = !organizationCityDropdownOpen;
    const cityMenu = document.getElementById('org-city-filter-menu');
    if (!cityMenu) return;
    cityMenu.classList.toggle('show', organizationCityDropdownOpen);
  }

  function toggleOrganizationCityFilterOption(event, encodedCity) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }
    const city = decodeURIComponent(encodedCity || '').trim();
    if (!city) return;
    const exists = organizationCityFilters.some(value => value.toLowerCase() === city.toLowerCase());
    if (exists) {
      organizationCityFilters = organizationCityFilters.filter(value => value.toLowerCase() !== city.toLowerCase());
    } else {
      organizationCityFilters = [...organizationCityFilters, city].sort((a, b) => a.localeCompare(b));
    }
    renderOrganizationCityFilter();
    renderOrganizationPicker();
  }

  function removeOrganizationCityFilter(event, encodedCity) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }
    const city = decodeURIComponent(encodedCity || '').trim().toLowerCase();
    if (!city) return;
    organizationCityFilters = organizationCityFilters.filter(value => value.toLowerCase() !== city);
    renderOrganizationCityFilter();
    renderOrganizationPicker();
  }

  function clearOrganizationCityFilters() {
    organizationCityFilters = [];
    renderOrganizationCityFilter();
    renderOrganizationPicker();
  }

  function renderOrganizationPicker() {
    const listEl = document.getElementById('org-picker-list');
    if (!listEl) return;
    const items = getOrganizationModalItems();
    if (items.length === 0) {
      listEl.innerHTML = '<p style="color:var(--muted);padding:.9rem 0">Nema restorana za prikaz.</p>';
      return;
    }
    listEl.innerHTML = `
      <div class="org-picker-grid">
        ${items.map(org => {
          const selected = Number(selectedOrganizationId) === Number(org.id);
          const status = computeOrganizationOrderability(org);
          return `
            <div class="org-picker-card ${selected ? 'active' : ''}" onclick="selectOrganizationFromModal(${org.id})">
              <span class="org-selected-check">${selected ? '&#10003;' : ''}</span>
              <div class="org-picker-title">${escapeHtml(org.name)}</div>
              <div class="org-picker-meta">${escapeHtml(org.city || '-')} ${org.address ? ` - ${escapeHtml(org.address)}` : ''}</div>
              <div class="org-picker-chip-row">
                <span class="org-open-chip ${status.canOrderNow ? 'open' : 'closed'}">${status.canOrderNow ? 'Narudžba moguća' : 'Narudžba blokirana'}</span>
                <button type="button" class="fav-btn ${org.is_favorite ? 'active' : ''}" onclick="toggleOrganizationFavorite(event, ${org.id}, ${org.is_favorite ? 'true' : 'false'})">${org.is_favorite ? 'Favorit' : 'Dodaj favorit'}</button>
              </div>
              ${status.canOrderNow ? '' : `<div class="org-picker-meta" style="margin-top:.35rem">${escapeHtml(status.reason || '')}</div>`}
            </div>
          `;
        }).join('')}
      </div>
    `;
  }

  async function openOrganizationPickerModal() {
    if (!currentUser) return;
    organizationModalTab = 'all';
    organizationSearchTerm = '';
    organizationCityFilters = [];
    closeOrganizationCityDropdown();
    document.getElementById('org-picker-modal').style.display = 'grid';
    const searchInput = document.getElementById('org-search-input');
    if (searchInput) searchInput.value = '';
    await loadOrganizationCatalog();
    renderOrganizationCityFilter();
    setOrganizationModalTab('all');
    renderOrganizationPicker();
  }

  function closeOrganizationPickerModal(event) {
    if (event && event.target !== event.currentTarget) return;
    closeOrganizationCityDropdown();
    document.getElementById('org-picker-modal').style.display = 'none';
  }

  function setOrganizationModalTab(tab) {
    organizationModalTab = tab === 'favorites' ? 'favorites' : 'all';
    document.getElementById('org-tab-all').classList.toggle('active', organizationModalTab === 'all');
    document.getElementById('org-tab-favorites').classList.toggle('active', organizationModalTab === 'favorites');
    renderOrganizationPicker();
  }

  function onOrganizationSearchInput(value) {
    organizationSearchTerm = value || '';
    renderOrganizationPicker();
  }

  async function toggleOrganizationFavorite(event, organizationId, isFavorite) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }
    const res = await fetch(`/organizations/${organizationId}/favorite`, {
      method: isFavorite ? 'DELETE' : 'POST',
      headers: authHeaders(),
    });
    if (!res.ok && res.status !== 204) {
      showToast('Neuspjelo ažuriranje favorita.');
      return;
    }
    await loadOrganizationCatalog();
    renderOrganizationCityFilter();
    renderOrganizationPicker();
    refreshStudentSelectorUi();
  }

  async function selectOrganizationFromModal(organizationId) {
    const nextId = Number(organizationId);
    if (Number(selectedOrganizationId) === nextId) {
      closeOrganizationPickerModal();
      return;
    }
    if (Object.keys(cart).length > 0) {
      const ok = confirm('Promjena restorana će isprazniti košaricu. Nastaviti?');
      if (!ok) return;
      clearCart();
    }
    selectedOrganizationId = nextId;
    persistSelectedOrganizationId();
    closeOrganizationPickerModal();
    await loadMenu();
    await loadDashboardOrders();
    refreshStudentSelectorUi();
  }

  async function clearSelectedOrganization() {
    if (Object.keys(cart).length > 0) {
      const ok = confirm('Maknuti odabir restorana i isprazniti košaricu?');
      if (!ok) return;
      clearCart();
    }
    selectedOrganizationId = null;
    persistSelectedOrganizationId();
    await loadMenu({ skipAutoSelect: true });
    await loadDashboardOrders();
    refreshStudentSelectorUi();
  }

  function setOrganizationEditHours(hours) {
    const byDay = Object.fromEntries((hours || []).map(row => [Number(row.day_of_week), row]));
    activeOrganizationHours = WEEK_DAYS.map(({ day }) => {
      const row = byDay[day];
      return {
        day_of_week: day,
        is_closed: row ? !!row.is_closed : false,
        open_time: row && row.open_time ? row.open_time : '08:00',
        close_time: row && row.close_time ? row.close_time : '20:00',
      };
    });
  }

  function onOrgHourClosedChange(day, checked) {
    const row = activeOrganizationHours.find(item => item.day_of_week === day);
    if (!row) return;
    row.is_closed = !!checked;
    renderOrganizationHoursEditor();
  }

  function onOrgHourTimeChange(day, field, value) {
    const row = activeOrganizationHours.find(item => item.day_of_week === day);
    if (!row) return;
    row[field] = value;
  }

  function renderOrganizationHoursEditor() {
    const grid = document.getElementById('org-edit-hours-grid');
    if (!grid) return;
    grid.innerHTML = WEEK_DAYS.map(({ day, label }) => {
      const row = activeOrganizationHours.find(item => item.day_of_week === day) || {
        day_of_week: day,
        is_closed: false,
        open_time: '08:00',
        close_time: '20:00',
      };
      const disabled = row.is_closed ? 'disabled' : '';
      return `
        <div class="hours-row">
          <div class="hours-day">${label}</div>
          <div class="hours-fields">
            <input type="time" value="${escapeHtml(row.open_time || '08:00')}" ${disabled} onchange="onOrgHourTimeChange(${day}, 'open_time', this.value)" />
            <input type="time" value="${escapeHtml(row.close_time || '20:00')}" ${disabled} onchange="onOrgHourTimeChange(${day}, 'close_time', this.value)" />
            <label class="hours-closed"><input type="checkbox" ${row.is_closed ? 'checked' : ''} onchange="onOrgHourClosedChange(${day}, this.checked)" /> Zatvoreno</label>
          </div>
        </div>
      `;
    }).join('');
  }

  async function openOrganizationEditModal(organizationId = null) {
    if (!isStaffRole()) return;
    const fallbackOrgId = getActiveStaffOrganizationId();
    const targetId = Number(organizationId || fallbackOrgId || (currentUser && currentUser.organization_id) || 0);
    if (!targetId) {
      showToast('Nije pronadena organizacija za uredjivanje.');
      return;
    }
    const res = await fetch(`/organizations/${targetId}`, { headers: authHeaders() });
    if (!res.ok) {
      showToast('Neuspjelo učitavanje organizacije.');
      return;
    }
    const org = await res.json();
    activeOrganizationEditId = org.id;
    document.getElementById('org-edit-name').value = org.name || '';
    document.getElementById('org-edit-address').value = org.address || '';
    document.getElementById('org-edit-city').value = org.city || '';
    document.getElementById('org-edit-phone').value = org.phone || '';
    document.getElementById('org-edit-title-sub').textContent = `${org.name}${org.city ? ` ⬢ ${org.city}` : ''}`;
    document.getElementById('org-edit-error').textContent = '';
    setOrganizationEditHours(org.working_hours || []);
    renderOrganizationHoursEditor();
    document.getElementById('org-edit-modal').style.display = 'grid';
  }

  function openOrganizationEditFromProfile() {
    const selector = document.getElementById('profile-edit-org-select');
    const targetId = selector && selector.value
      ? Number(selector.value)
      : Number(getActiveStaffOrganizationId() || (currentUser && currentUser.organization_id));
    if (!targetId) return;
    void openOrganizationEditModal(targetId);
  }

  function onProfileOrganizationSelectChange(value) {
    const targetId = Number(value);
    if (!targetId) return;
    void setActiveStaffOrganization(targetId, { reloadMenu: true, reloadUsers: true });
  }

  function closeOrganizationEditModal(event) {
    if (event && event.target !== event.currentTarget) return;
    document.getElementById('org-edit-modal').style.display = 'none';
    activeOrganizationEditId = null;
  }

  async function saveOrganizationEdit() {
    if (!activeOrganizationEditId) return;
    const errEl = document.getElementById('org-edit-error');
    errEl.textContent = '';
    const name = document.getElementById('org-edit-name').value.trim();
    const address = document.getElementById('org-edit-address').value.trim() || null;
    const city = document.getElementById('org-edit-city').value.trim() || null;
    const phone = document.getElementById('org-edit-phone').value.trim() || null;
    if (!name) {
      errEl.textContent = 'Naziv organizacije je obavezan.';
      return;
    }
    const workingHours = activeOrganizationHours.map(row => {
      if (row.is_closed) {
        return { day_of_week: row.day_of_week, is_closed: true, open_time: null, close_time: null };
      }
      return {
        day_of_week: row.day_of_week,
        is_closed: false,
        open_time: row.open_time || null,
        close_time: row.close_time || null,
      };
    });
    const invalidDay = workingHours.find(row => !row.is_closed && (!row.open_time || !row.close_time || row.open_time >= row.close_time));
    if (invalidDay) {
      errEl.textContent = 'Provjerite radno vrijeme: otvoreni dan mora imati ispravan raspon sati.';
      return;
    }
    const res = await fetch(`/organizations/${activeOrganizationEditId}`, {
      method: 'PUT',
      headers: authHeaders(),
      body: JSON.stringify({ name, address, city, phone, working_hours: workingHours }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      errEl.textContent = err.detail || 'Neuspjelo spremanje organizacije.';
      return;
    }
    const updatedOrganization = await res.json();
    if (currentUser) {
      if (Array.isArray(currentUser.organizations)) {
        currentUser.organizations = currentUser.organizations.map(org =>
          Number(org.id) === Number(updatedOrganization.id)
            ? { ...org, ...updatedOrganization }
            : org
        );
      }
      if (Number(currentUser.organization_id) === Number(updatedOrganization.id)) {
        currentUser.organization = { ...(currentUser.organization || {}), ...updatedOrganization };
      }
    }
    organizationCatalog = organizationCatalog.map(org =>
      Number(org.id) === Number(updatedOrganization.id)
        ? { ...org, ...updatedOrganization }
        : org
    );
    closeOrganizationEditModal();
    showToast('Organizacija je uspješno ažurirana.');
    await initApp();
    if (document.getElementById('profile-section').style.display !== 'none') {
      await showTab('profile');
    }
  }

  async function saveProfileBasics() {
    const firstName = document.getElementById('profile-edit-first')?.value.trim() || null;
    const lastName = document.getElementById('profile-edit-last')?.value.trim() || null;
    const res = await fetch('/auth/me', {
      method: 'PATCH',
      headers: authHeaders(),
      body: JSON.stringify({ first_name: firstName, last_name: lastName }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      showToast(err.detail || 'Neuspjelo spremanje profila.');
      return;
    }
    currentUser = await res.json();
    showToast('Profil uspješno ažuriran.');
    await renderProfilePage();
  }

  async function removeProfileAvatar() {
    const res = await fetch('/auth/me/avatar', {
      method: 'DELETE',
      headers: authHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      showToast(err.detail || 'Neuspjelo uklanjanje avatara.');
      return;
    }
    currentUser = await res.json();
    syncAvatarUIFromCurrentUser();
    showToast('Avatar je uklonjen.');
    await renderProfilePage();
  }

  async function changeProfilePassword() {
    const currentPassword = document.getElementById('profile-pass-current')?.value || '';
    const newPassword = document.getElementById('profile-pass-new')?.value || '';
    const confirmPassword = document.getElementById('profile-pass-confirm')?.value || '';
    if (!currentPassword || !newPassword || !confirmPassword) {
      showToast('Unesite sve lozinke za promjenu.');
      return;
    }
    if (newPassword !== confirmPassword) {
      showToast('Nova lozinka i potvrda se ne podudaraju.');
      return;
    }
    const res = await fetch('/auth/me/password', {
      method: 'PATCH',
      headers: authHeaders(),
      body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      showToast(err.detail || 'Neuspjela promjena lozinke.');
      return;
    }
    document.getElementById('profile-pass-current').value = '';
    document.getElementById('profile-pass-new').value = '';
    document.getElementById('profile-pass-confirm').value = '';
    showToast('Lozinka je uspješno promijenjena.');
  }

  async function moveStaffToOrganization(adminId) {
    const selectEl = document.getElementById(`profile-move-target-${adminId}`);
    if (!selectEl) return;
    const targetOrgId = Number(selectEl.value);
    const admin = ownerAdmins.find(item => Number(item.id) === Number(adminId));
    if (!admin || !targetOrgId || Number(admin.organization_id) === targetOrgId) return;
    const res = await fetch(`/auth/admins/${adminId}/move-organization`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({
        from_organization_id: admin.organization_id,
        to_organization_id: targetOrgId,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      showToast(err.detail || 'Neuspjelo premještanje djelatnika.');
      return;
    }
    showToast('Djelatnik je premješten.');
    await loadOwnerAdmins();
    await loadOrganizationUsers();
    await renderProfilePage();
  }

  async function renderProfilePage() {
    if (!currentUser) return;

    // Always fetch latest data so name and subsidy are current (e.g. after ISSP sync)
    const meRes = await fetch('/auth/me', { headers: authHeaders() });
    if (meRes.ok) {
      currentUser = await meRes.json();
      // Sync nav subsidy badge
      const navSubsidy = document.getElementById('nav-subsidy');
      if (navSubsidy && currentUser.subsidy_remaining != null) {
        navSubsidy.textContent = 'Subvencija: ' + fmt(Number(currentUser.subsidy_remaining));
        navSubsidy.style.display = '';
      }
    }

    await ensureProfileDataLoaded();

    const displayName = userDisplayName(currentUser) || 'Korisnik';
    document.getElementById('profile-user-name').textContent = displayName;
    document.getElementById('profile-user-role').textContent = roleLabel(currentUser.role);
    const roleBadgeEl = document.getElementById('profile-role-badge');
    if (roleBadgeEl) {
      roleBadgeEl.textContent = roleLabel(currentUser.role);
      roleBadgeEl.className = `profile-role-badge ${roleBadgeClass(currentUser.role)}`;
    }
    const orgPillEl = document.getElementById('profile-org-pill');
    if (orgPillEl) {
      orgPillEl.textContent = `Organizacija: ${getOrganizationName(currentUser)}`;
    }
    syncAvatarUIFromCurrentUser();
    const modeBadgeEl = document.getElementById('profile-mode-badge');
    const modeNoteEl = document.getElementById('profile-mode-note');
    if (modeBadgeEl && modeNoteEl) {
      if (isStaffRole()) {
        modeBadgeEl.textContent = 'Aktivni profil';
        modeNoteEl.textContent = 'Možete urediti ime, prezime, profilnu sliku i lozinku.';
      } else {
        modeBadgeEl.textContent = 'Profil studenta';
        modeNoteEl.textContent = 'Možete urediti ime i prezime pritiskom na "Spremi profil".';
      }
    }

    const nameDisplay = userDisplayName(currentUser) || 'Nije postavljeno';
    const detailRows = normalizeRole(currentUser.role) === 'student'
      ? [
          ['Ime i prezime', nameDisplay],
          ['Broj studentske kartice', currentUser.student_card_number || '-'],
          ['ESI', currentUser.student_esi || '-'],
          ['Fakultet', (isspProfileData && isspProfileData.faculty) ? isspProfileData.faculty : '-'],
          ['Preostale subvencije', currentUser.subsidy_remaining != null ? fmt(Number(currentUser.subsidy_remaining)) : 'Nije dostupno (poveži ISSP)'],
          ['Izvor studentskih podataka', (isspProfileData && isspProfileData.source) ? String(isspProfileData.source).toUpperCase() : '-'],
        ]
      : [
          ['Ime i prezime', nameDisplay],
          ['Email', currentUser.email || '-'],
          ['Organizacija / restoran', getOrganizationName(currentUser)],
          ['Rola', roleLabel(currentUser.role)],
        ];

    document.getElementById('profile-details').innerHTML = `
      <div class="profile-meta-grid">
        ${detailRows.map(([label, value]) => {
          const orgClickable = isStaffRole() && label.startsWith('Organizacija');
          return `
            <div class="profile-meta-item ${orgClickable ? 'org-clickable' : ''}" ${orgClickable ? 'onclick="openOrganizationEditModal(getActiveStaffOrganizationId())"' : ''}>
              <span class="profile-meta-label">${escapeHtml(label)}</span>
              <span class="profile-meta-value">${escapeHtml(value)}</span>
              ${orgClickable ? '<div class="helper-note tight">Kliknite za uredjivanje organizacije</div>' : ''}
            </div>
          `;
        }).join('')}
      </div>
    `;

    const avatarControls = document.getElementById('profile-avatar-controls');
    const inlineControls = document.getElementById('profile-inline-controls');
    avatarControls.innerHTML = '';
    inlineControls.innerHTML = '';

    if (isStaffRole()) {
      avatarControls.innerHTML = `
        <input class="visually-hidden-file" type="file" id="profile-avatar-input" accept="image/jpeg,image/png,image/webp" onchange="onProfileAvatarSelected(event)" />
        <div class="profile-inline-actions">
          <button type="button" class="btn btn-dark btn-sm" onclick="document.getElementById('profile-avatar-input').click()">Promijeni sliku</button>
          <button type="button" class="btn btn-ghost btn-sm" onclick="removeProfileAvatar()">Ukloni sliku</button>
        </div>
      `;
    }

    const editableOrganizations = isStaffRole() ? (currentUser.organizations || []) : [];
    const selectedProfileOrgId = Number(getActiveStaffOrganizationId() || (currentUser && currentUser.organization_id) || 0);
    const profileOrgSelector = editableOrganizations.length > 1
      ? `
        <select id="profile-edit-org-select" onchange="onProfileOrganizationSelectChange(this.value)">
          ${editableOrganizations.map(org => `<option value="${Number(org.id)}" ${Number(org.id) === selectedProfileOrgId ? 'selected' : ''}>${escapeHtml(org.name || `Organizacija #${org.id}`)}</option>`).join('')}
        </select>
      `
      : '';

    inlineControls.innerHTML = `
      <div class="profile-editor-grid">
        <div class="form-group" style="margin:0">
          <label>Ime</label>
          <input type="text" id="profile-edit-first" value="${escapeHtml(currentUser.first_name || '')}" />
        </div>
        <div class="form-group" style="margin:0">
          <label>Prezime</label>
          <input type="text" id="profile-edit-last" value="${escapeHtml(currentUser.last_name || '')}" />
        </div>
      </div>
      <div class="profile-inline-actions">
        <button type="button" class="btn btn-primary btn-sm" onclick="saveProfileBasics()">Spremi profil</button>
        ${isStaffRole() ? `${profileOrgSelector}<button type="button" class="btn btn-ghost btn-sm" onclick="openOrganizationEditFromProfile()">Uredi organizaciju</button>` : ''}
        <button type="button" class="btn btn-ghost btn-sm" onclick="logout()">Odjava</button>
      </div>
      ${isStaffRole() ? `
        <div class="profile-section-title" style="margin-top:1rem">Promjena lozinke</div>
        <div class="profile-editor-grid">
          <div class="form-group" style="margin:0">
            <label>Trenutna lozinka</label>
            <input type="password" id="profile-pass-current" />
          </div>
          <div class="form-group" style="margin:0">
            <label>Nova lozinka</label>
            <input type="password" id="profile-pass-new" />
          </div>
          <div class="form-group" style="margin:0">
            <label>Potvrda nove lozinke</label>
            <input type="password" id="profile-pass-confirm" />
          </div>
        </div>
        <div class="profile-inline-actions">
          <button type="button" class="btn btn-dark btn-sm" onclick="changeProfilePassword()">Promijeni lozinku</button>
        </div>
      ` : ''}
    `;

    const ownerAdvanced = document.getElementById('profile-owner-advanced');
    if (!isOwnerRole()) {
      ownerAdvanced.style.display = 'none';
      ownerAdvanced.innerHTML = '';
      return;
    }

    const organizations = buildOrganizationBuckets(orgUsers);
    const ownerOrgOptions = (currentUser.organizations || []).map(org => ({
      id: Number(org.id),
      name: org.name || `Organizacija #${org.id}`,
    }));

    ownerAdvanced.style.display = '';
    ownerAdvanced.innerHTML = `
      <div class="profile-card theme-transition">
        <h3 class="profile-section-title">Organizacijski prikaz</h3>
        ${organizations.length === 0 ? `
          <p class="helper-note">Nema organizacijskih podataka za prikaz.</p>
        ` : `
          <div class="org-card-list">
            ${organizations.map(([orgName, users]) => {
              const activeCount = users.filter(user => user.is_active).length;
              const staffCount = users.filter(user => user.role !== 'student').length;
              const studentCount = users.length - staffCount;
              const visibleStaff = users.filter(user => user.role !== 'student').slice(0, 5);
              return `
                <div class="org-card">
                  <h4>${escapeHtml(orgName)}</h4>
                  <div class="org-stat-grid">
                    <div class="org-stat">
                      <span class="org-stat-label">Korisnici</span>
                      <span class="org-stat-value">${users.length}</span>
                    </div>
                    <div class="org-stat">
                      <span class="org-stat-label">Aktivni</span>
                      <span class="org-stat-value">${activeCount}</span>
                    </div>
                    <div class="org-stat">
                      <span class="org-stat-label">Studenti / Staff</span>
                      <span class="org-stat-value">${studentCount}/${staffCount}</span>
                    </div>
                  </div>
                  <div class="org-chip-row">
                    ${visibleStaff.map(user => `<span class="org-chip">${escapeHtml(userDisplayName(user))}</span>`).join('') || '<span class="helper-note tight">Bez djelatnika</span>'}
                  </div>
                </div>
              `;
            }).join('')}
          </div>
        `}
      </div>
      <div class="profile-card profile-admin-table theme-transition">
        <h3 class="profile-section-title">Premještanje djelatnika</h3>
        ${ownerAdmins.length === 0 ? `
          <p class="helper-note">Nema djelatnika za prikaz.</p>
        ` : `
          <div class="table-scroll">
            <table class="admin-table">
              <thead>
                <tr><th>Djelatnik</th><th>Trenutna organizacija</th><th>Ciljana organizacija</th><th>Akcija</th></tr>
              </thead>
              <tbody>
                ${ownerAdmins.map(admin => `
                  <tr>
                    <td>${escapeHtml(userDisplayName(admin))}<div style="font-size:.75rem;color:var(--muted)">${escapeHtml(admin.email)}</div></td>
                    <td>${escapeHtml(getOrganizationName(admin))}</td>
                    <td>
                      <select id="profile-move-target-${admin.id}">
                        ${ownerOrgOptions.map(org => `<option value="${org.id}" ${Number(admin.organization_id) === org.id ? 'selected' : ''}>${escapeHtml(org.name)}</option>`).join('')}
                      </select>
                    </td>
                    <td><button type="button" class="btn btn-primary btn-sm" onclick="moveStaffToOrganization(${admin.id})">Premjesti</button></td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        `}
      </div>
    `;
  }

  function setLoginMode(mode) {
    loginMode = mode === 'owner' ? 'owner' : (mode === 'staff' ? 'staff' : 'student');
    const cardInput = document.getElementById('card-input');
    const staffUsernameInput = document.getElementById('staff-username-input');
    const label = document.getElementById('login-identifier-label');
    const useUsername = loginMode !== 'student';

    label.textContent = useUsername ? 'Korisničko ime' : 'Broj studentske iskaznice';
    cardInput.style.display = useUsername ? 'none' : '';
    staffUsernameInput.style.display = useUsername ? '' : 'none';
    staffUsernameInput.placeholder = loginMode === 'owner' ? 'admin' : 'djelatnik';

    document.querySelectorAll('.login-role-choice').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.mode === loginMode);
    });
    setRoleTheme(loginMode);
    document.getElementById('login-error').textContent = '';
  }

  function setAdminImagePreview(src, hasImage) {
    const preview = document.getElementById('af-image-preview');
    const dropzone = document.getElementById('af-dropzone');
    preview.src = src || FALLBACK_IMAGE;
    dropzone.classList.toggle('has-image', !!hasImage);
    if (!hasImage) dropzone.classList.remove('dragover');
  }

  function previewAdminImage() {
    const input = document.getElementById('af-image');
    const file = input.files && input.files[0];
    if (!file) {
      setAdminImagePreview(FALLBACK_IMAGE, false);
      return;
    }
    const reader = new FileReader();
    reader.onload = () => { setAdminImagePreview(reader.result, true); };
    reader.readAsDataURL(file);
  }

  function onAdminDropzoneDragOver(event) {
    event.preventDefault();
    document.getElementById('af-dropzone').classList.add('dragover');
  }

  function onAdminDropzoneDragLeave(event) {
    event.preventDefault();
    if (event.relatedTarget && event.currentTarget.contains(event.relatedTarget)) return;
    document.getElementById('af-dropzone').classList.remove('dragover');
  }

  function onAdminDropzoneDrop(event) {
    event.preventDefault();
    const dropzone = document.getElementById('af-dropzone');
    dropzone.classList.remove('dragover');
    const files = event.dataTransfer && event.dataTransfer.files;
    if (!files || files.length === 0) return;
    const input = document.getElementById('af-image');
    try {
      if (typeof DataTransfer !== 'undefined') {
        const dt = new DataTransfer();
        dt.items.add(files[0]);
        input.files = dt.files;
      } else {
        input.files = files;
      }
    } catch {
      return;
    }
    previewAdminImage();
  }

  //  AUTH TAB SWITCH 

  function switchAuthTab(tab) {
    document.getElementById('login-form').style.display    = tab === 'login' ? '' : 'none';
    document.getElementById('register-form').style.display = tab === 'register' ? '' : 'none';
    document.getElementById('auth-tab-login').classList.toggle('active',    tab === 'login');
    document.getElementById('auth-tab-register').classList.toggle('active', tab === 'register');
    document.getElementById('login-error').textContent    = '';
    document.getElementById('register-error').textContent = '';
  }

  //  AUTH 

  async function doLogin() {
    const mode = loginMode;
    const isStaffLogin = mode === 'staff' || mode === 'owner';
    const identifier = isStaffLogin
      ? document.getElementById('staff-username-input').value.trim()
      : document.getElementById('card-input').value.trim();
    const pass = document.getElementById('pass-input').value;
    document.getElementById('login-error').textContent = '';
    if (!identifier || !pass) {
      document.getElementById('login-error').textContent = 'Unesite korisničke podatke.';
      return;
    }
    try {
      const endpoint = isStaffLogin ? '/auth/login/staff' : '/auth/login/student';
      const res = await fetch(endpoint, {
        method: 'POST',
        body: new URLSearchParams({ username: identifier, password: pass }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        document.getElementById('login-error').textContent = err.detail || 'Neispravni podaci';
        return;
      }
      const data = await res.json();
      token = data.access_token;
      localStorage.setItem('token', token);
      await initApp();
    } catch {
      document.getElementById('login-error').textContent = 'Greška pri spajanju';
    }
  }

  async function doRegister() {
    const errEl = document.getElementById('register-error');
    errEl.textContent = '';
    const first_name = document.getElementById('reg-first').value.trim() || null;
    const last_name  = document.getElementById('reg-last').value.trim() || null;
    const email      = document.getElementById('reg-email').value.trim();
    const card       = document.getElementById('reg-card').value.trim();
    const esi        = document.getElementById('reg-esi').value.trim();
    const pass       = document.getElementById('reg-pass').value;
    const pass2      = document.getElementById('reg-pass2').value;

    if (!email || !card || !esi || !pass) { errEl.textContent = 'Ispunite sva obavezna polja.'; return; }
    if (pass !== pass2) { errEl.textContent = 'Lozinke se ne podudaraju.'; return; }
    if (pass.length < 6) { errEl.textContent = 'Lozinka mora imati najmanje 6 znakova.'; return; }

    try {
      const res = await fetch('/auth/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password: pass, student_card_number: card, student_esi: esi, first_name, last_name }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        errEl.textContent = err.detail || 'Greška pri registraciji';
        return;
      }
      const loginRes = await fetch('/auth/login/student', {
        method: 'POST',
        body: new URLSearchParams({ username: card, password: pass }),
      });
      if (!loginRes.ok) {
        switchAuthTab('login');
        showToast('Registracija uspješna! Prijavite se.');
        return;
      }
      const data = await loginRes.json();
      token = data.access_token;
      localStorage.setItem('token', token);
      await initApp();
    } catch {
      errEl.textContent = 'Greška pri spajanju';
    }
  }

  function logout() {
    token = '';
    currentUser = null;
    orgUsers = [];
    ownerAdmins = [];
    menuItems = [];
    selectedOrganizationId = null;
    organizationCatalog = [];
    organizationModalTab = 'all';
    organizationSearchTerm = '';
    organizationCityFilters = [];
    organizationCityDropdownOpen = false;
    activeStaffOrganizationId = null;
    activeOrganizationEditId = null;
    activeOrganizationHours = [];
    selectedCategory = '';
    selectedCategoryToken = '';
    activeView = 'home';
    menuChipFilter = 'all';
    isspLinkMode = 'manual';
    isspProfileData = null;
    favoriteMenuItems = {};
    mealRatings = {};
    userMealRatings = {};
    personalOrders = [];
    globalOrders = [];
    popularItemStats = [];
    recommendedCarouselIndex = 0;
    selectedRatingItemId = null;
    pendingRatingValue = 5;
    localStorage.removeItem('token');
    closeMobileSidebar();
    document.body.classList.remove('app-authenticated');
    setRoleTheme('student');
    applyRoleBasedNavigationVisibility();
    document.getElementById('app-page').style.display  = 'none';
    document.getElementById('login-page').style.display = 'flex';
    document.getElementById('nav-profile-btn').style.display = 'none';
    document.getElementById('nav-subsidy').style.display = 'none';
    ['tab-home', 'tab-menu', 'tab-orders', 'tab-favorites', 'tab-admin', 'tab-users', 'tab-profile'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.classList.remove('active');
    });
    document.getElementById('owner-admin-management').style.display = 'none';
    document.getElementById('users-section').style.display = 'none';
    document.getElementById('profile-section').style.display = 'none';
    document.getElementById('favorites-section').style.display = 'none';
    document.getElementById('org-picker-modal').style.display = 'none';
    document.getElementById('org-edit-modal').style.display = 'none';
    closeMiniCart();
    applyAvatarToUI('');
    setLoginMode('student');
    cart = {};
    refreshCart();
  }

  //  INIT 

  async function initApp() {
    const me = await fetch('/auth/me', { headers: authHeaders() });
    if (!me.ok) { logout(); return; }
    currentUser = await me.json();
    isspLinkMode = 'manual';
    document.body.classList.add('app-authenticated');
    setRoleTheme(roleBadgeClass(currentUser.role));
    applyRoleBasedNavigationVisibility();
    selectedCategory = '';
    selectedCategoryToken = '';
    menuChipFilter = 'all';
    loadUserUiState();
    setTodayMenuDate();
    document.getElementById('hero-user-name').textContent = userDisplayName(currentUser).split(' ')[0] || 'Prijatelju';

    document.getElementById('nav-profile-btn').style.display = '';
    document.getElementById('nav-subsidy').style.display = 'none';
    hydrateISSPProfileFromStorage();
    syncAvatarUIFromCurrentUser();

    if (currentUser.subsidy_remaining != null) {
      const el = document.getElementById('nav-subsidy');
      el.textContent = 'Subvencija: ' + fmt(currentUser.subsidy_remaining);
      el.style.display = '';
    }

    document.getElementById('owner-admin-management').style.display = 'none';
    const legacyOwnerPanel = document.getElementById('owner-admin-management-legacy');
    if (legacyOwnerPanel) legacyOwnerPanel.style.display = 'none';

    if (isStaffRole()) {
      syncStaffOrganizationFromUser();
    }
    if (isOwnerRole()) {
      document.getElementById('owner-admin-management').style.display = '';
      loadOwnerAdmins();
    }
    renderStaffOrganizationSelector();

    document.getElementById('login-page').style.display = 'none';
    document.getElementById('app-page').style.display   = 'block';
    document.getElementById('pickup-input').value = minPickupTime();
    document.getElementById('pickup-input').min   = minPickupTime();
    if (isStudentRole()) {
      const defaultStudentOrgId = Number(selectedOrganizationId || currentUser.organization_id || 0) || null;
      selectedOrganizationId = defaultStudentOrgId;
      if (selectedOrganizationId) persistSelectedOrganizationId();
      activeStaffOrganizationId = null;
    } else {
      selectedOrganizationId = getActiveStaffOrganizationId();
    }
    cart = {};

    // Check ISSP service status
    await checkISSPStatus();

    await loadMenu();
    await loadRatingsData();
    await loadDashboardOrders();
    refreshStudentSelectorUi();
    refreshCart();
    await showTab(readTabFromHash(), { updateHash: true });
  }

  //  MENU 

  async function loadMenu({ skipAutoSelect = false } = {}) {
    if (isStudentRole() && !skipAutoSelect) {
      await ensureStudentOrganizationSelection();
    }
    const availableOnly = 'false';
    const params = new URLSearchParams({ available_only: availableOnly });
    const orgIdForMenu = isStudentRole()
      ? selectedOrganizationId
      : getActiveStaffOrganizationId();

    if (isStudentRole() && !orgIdForMenu) {
      menuItems = [];
      buildSidebar();
      renderMenu();
      renderFavorites();
      renderRecommendedPanel();
      renderPopularPanel();
      renderExperienceWidget();
      renderNutritionPanel();
      refreshStudentSelectorUi();
      showToast('Odaberite restoran za prikaz jelovnika.');
      return;
    }

    if (isStaffRole() && !orgIdForMenu) {
      menuItems = [];
      buildSidebar();
      renderMenu();
      renderFavorites();
      renderRecommendedPanel();
      renderPopularPanel();
      renderExperienceWidget();
      renderNutritionPanel();
      showToast('Nije odabrana organizacija za prikaz jelovnika.');
      return;
    }

    if (orgIdForMenu) params.set('organization_id', String(orgIdForMenu));
    const res = await fetch('/menu/items?' + params.toString(), { headers: authHeaders() });
    if (!res.ok) {
      menuItems = [];
      buildSidebar();
      renderMenu();
      renderFavorites();
      renderRecommendedPanel();
      renderPopularPanel();
      renderExperienceWidget();
      renderNutritionPanel();
      showToast('Greška pri učitavanju jelovnika.');
      return;
    }

    menuItems = await res.json();
    if (selectedCategoryToken && !menuItems.some(item => normalizeCategoryToken(item.category) === selectedCategoryToken)) {
      selectedCategory = '';
      selectedCategoryToken = '';
    }
    updateHeroVisual();
    if (currentUser) {
      await loadOrganizationCatalog();
    }

    buildSidebar();
    renderMenu();
    renderFavorites();
    renderRecommendedPanel();
    renderPopularPanel();
    renderExperienceWidget();
    renderNutritionPanel();
    refreshStudentSelectorUi();
  }

  function applyMenuChipFilter(type) {
    menuChipFilter = 'all';
    renderMenu();
  }

  function getQuickOrderItemIds() {
    const counter = {};
    personalOrders.forEach(order => {
      (order.items || []).forEach(item => {
        const key = Number(item.menu_item_id);
        counter[key] = (counter[key] || 0) + Number(item.quantity || 0);
      });
    });
    return Object.entries(counter)
      .sort((a, b) => b[1] - a[1])
      .map(([itemId]) => Number(itemId))
      .filter(Boolean)
      .slice(0, 8);
  }

  function getPopularItemIds() {
    if (Array.isArray(popularItemStats) && popularItemStats.length > 0) {
      return popularItemStats
        .slice()
        .sort((a, b) => Number(b.order_count || 0) - Number(a.order_count || 0))
        .map(row => Number(row.menu_item_id))
        .filter(Boolean)
        .slice(0, 8);
    }

    const source = globalOrders.length > 0 ? globalOrders : personalOrders;
    const counter = {};
    source.forEach(order => {
      (order.items || []).forEach(item => {
        const key = Number(item.menu_item_id);
        counter[key] = (counter[key] || 0) + Number(item.quantity || 0);
      });
    });
    return Object.entries(counter)
      .sort((a, b) => b[1] - a[1])
      .map(([itemId]) => Number(itemId))
      .filter(Boolean)
      .slice(0, 8);
  }

  function getPersonalizedItemIds() {
    const quickOrderIds = getQuickOrderItemIds();
    const favoriteIds = menuItems
      .filter(item => isItemFavorite(item.id))
      .map(item => Number(item.id))
      .filter(Boolean);
    const ratedIds = Object.entries(userMealRatings)
      .sort((a, b) => Number(b[1] || 0) - Number(a[1] || 0))
      .map(([itemId]) => Number(itemId))
      .filter(Boolean);
    return [...quickOrderIds, ...favoriteIds, ...ratedIds];
  }

  function applyMenuChipDataset(items) {
    return items;
  }

  function getMenuDatasetForActiveView() {
    if (isStudentRole() && activeView === 'home') {
      return menuItems.filter(item => !!item.is_available);
    }
    return [...menuItems];
  }

  function updateHeroVisual() {
    const heroImg = document.getElementById('hero-food-image');
    if (!heroImg) return;
    const preferredItem = menuItems.find(item =>
      item && typeof item.image_url === 'string' && item.image_url.trim() && item.image_url !== FALLBACK_IMAGE
    );
    const src = preferredItem ? preferredItem.image_url : HERO_FOOD_FALLBACK;
    heroImg.src = src;
    heroImg.onerror = function onHeroImageError() {
      this.onerror = null;
      this.src = HERO_FOOD_FALLBACK;
    };
  }

  function sortCategoriesByPriority(categories) {
    const normalized = categories
      .map(category => String(category || '').trim())
      .filter(Boolean);
    return normalized.sort((a, b) => {
      const tokenA = normalizeCategoryToken(a);
      const tokenB = normalizeCategoryToken(b);
      const indexA = Object.prototype.hasOwnProperty.call(CATEGORY_PRIORITY_INDEX, tokenA)
        ? CATEGORY_PRIORITY_INDEX[tokenA]
        : Number.MAX_SAFE_INTEGER;
      const indexB = Object.prototype.hasOwnProperty.call(CATEGORY_PRIORITY_INDEX, tokenB)
        ? CATEGORY_PRIORITY_INDEX[tokenB]
        : Number.MAX_SAFE_INTEGER;
      if (indexA !== indexB) return indexA - indexB;
      return a.localeCompare(b, 'hr-HR');
    });
  }

  function buildSidebar() {
    const dataset = getMenuDatasetForActiveView();
    const categoryMap = new Map();
    dataset.forEach(item => {
      const categoryName = String(item.category || '').trim();
      if (!categoryName) return;
      const token = normalizeCategoryToken(categoryName);
      if (!token || categoryMap.has(token)) return;
      categoryMap.set(token, categoryName);
    });
    const cats = sortCategoriesByPriority([...categoryMap.values()]);
    if (selectedCategoryToken && !categoryMap.has(selectedCategoryToken)) {
      selectedCategory = '';
      selectedCategoryToken = '';
    }
    const container = document.getElementById('sidebar-cats');
    if (!container) return;

    container.innerHTML = `
      <button class="menu-pill ${selectedCategoryToken === '' ? 'active' : ''}" data-token="" onclick="filterCategory('')">Sva jela</button>
      ${cats.map(c => {
        const token = normalizeCategoryToken(c);
        return `<button class="menu-pill ${selectedCategoryToken === token ? 'active' : ''}" data-token="${escapeHtml(token)}" onclick="filterCategory('${encodeURIComponent(token)}')">${escapeHtml(c)}</button>`;
      }).join('')}
    `;
  }

  function filterCategory(encodedToken) {
    const token = decodeURIComponent(encodedToken || '');
    selectedCategoryToken = token;
    selectedCategory = token;
    document.querySelectorAll('.menu-pill').forEach(el => {
      el.classList.toggle('active', (el.dataset.token || '') === token);
    });
    renderMenu();
  }

  function renderMenu() {
    const searchInput = document.getElementById('search-input');
    const search = searchInput ? searchInput.value.toLowerCase() : '';

    let items = getMenuDatasetForActiveView().filter(i => {
      const itemCategoryToken = normalizeCategoryToken(i.category);
      if (selectedCategoryToken && itemCategoryToken !== selectedCategoryToken) return false;
      if (search && !i.name.toLowerCase().includes(search) &&
          !(i.description || '').toLowerCase().includes(search)) return false;
      return true;
    });

    items = applyMenuChipDataset(items);
    items = items.sort((a, b) => a.name.localeCompare(b.name));

    const container = document.getElementById('menu-container');
    if (!container) return;
    if (items.length === 0) {
      container.innerHTML = '<p style="color:var(--muted);text-align:center;padding:2rem">Nema rezultata za odabrane filtere.</p>';
      return;
    }

    container.innerHTML = `<div class="dish-grid">${items.map(item => renderItemCard(item)).join('')}</div>`;
  }

  function renderFavorites() {
    const wrap = document.getElementById('favorites-container');
    const counter = document.getElementById('favorites-count-text');
    if (!wrap || !counter) return;

    const favorites = menuItems.filter(item => isItemFavorite(item.id));
    if (!favorites.length) {
      counter.textContent = 'Nema spremljenih jela.';
      wrap.innerHTML = '<p style="color:var(--muted);text-align:center;padding:1.2rem 0">Kliknite srce na jelu da ga spremite u favorite.</p>';
      return;
    }

    counter.textContent = `Spremljenih jela: ${favorites.length}`;
    wrap.innerHTML = `<div class="dish-grid">${favorites.map(item => renderItemCard(item)).join('')}</div>`;
  }

  function renderItemCard(item) {
    const nutrition = [
      item.calories_kcal != null ? item.calories_kcal + ' kcal' : null,
      item.protein_g != null     ? 'B: ' + item.protein_g + 'g' : null,
      item.carbs_g != null       ? 'UH: ' + item.carbs_g + 'g' : null,
      item.fat_g != null         ? 'M: ' + item.fat_g + 'g' : null,
    ].filter(Boolean).join(' • ');

    const qty = cart[item.id] || 0;
    const isOrderable = !!item.is_available && !!item.is_orderable;
    const ratingMeta = getItemRatingMeta(item.id);
    const ratingLabel = ratingMeta.count > 0
      ? `${ratingMeta.average.toFixed(1)} (${ratingMeta.count})`
      : 'Nema ocjena';
    const unavailableBadge = !item.is_available ? '<span class="dish-state-badge">Nedostupno</span>' : '';
    const lockReason = !item.is_available
      ? 'Artikal trenutno nije dostupan.'
      : (!item.is_orderable ? (getOrderBlockReason() || 'Narudžba trenutno nije moguća.') : '');

    return `
      <div class="dish-card ${isOrderable ? '' : 'is-locked'}" id="card-${item.id}">
        <div class="dish-media">
          <img class="item-image" src="${itemImageSrc(item)}" alt="${escapeHtml(item.name)}" onerror="this.src='${FALLBACK_IMAGE}'" />
          ${unavailableBadge}
          <button type="button" class="dish-favorite-btn ${isItemFavorite(item.id) ? 'active' : ''}" onclick="toggleItemFavorite(${item.id}, event)" title="Spremi u favorite">&#10084;</button>
        </div>
        <div class="dish-title">${escapeHtml(item.name)}</div>
        ${item.description ? `<div class="dish-desc">${escapeHtml(item.description)}</div>` : '<div class="dish-desc">Bez dodatnog opisa.</div>'}
        <div class="dish-nutrition">${nutrition || 'Nutritivne vrijednosti nisu dostupne.'}</div>
        <div class="dish-category">${escapeHtml(item.category || 'Ostalo')}</div>
        ${isOrderable ? `
          <div class="dish-footer">
            <span class="dish-price">${fmt(item.price)}</span>
            <span class="dish-rating">&#9733; ${ratingLabel}</span>
            ${qty === 0 ? `
              <button class="dish-add-btn" onclick="addToCart(${item.id})" title="Dodaj u košaricu">+</button>
            ` : `
              <div class="dish-qty">
                <button class="qty-btn" onclick="changeQty(${item.id}, -1)">-</button>
                <span class="qty-val">${qty}</span>
                <button class="qty-btn" onclick="changeQty(${item.id}, +1)">+</button>
              </div>
            `}
          </div>
        ` : `
          <div class="dish-footer">
            <span class="dish-price">${fmt(item.price)}</span>
            <span class="dish-rating">&#9733; ${ratingLabel}</span>
          </div>
          <div class="dish-lock-note">${escapeHtml(lockReason)}</div>
        `}
      </div>`;
  }
  function addToCart(id) {
    const item = menuItems.find(i => i.id === id);
    if (!item || !item.is_available || !item.is_orderable) {
      const reason = getOrderBlockReason() || 'Artikal trenutno nije moguće naručiti.';
      showToast(reason);
      return;
    }
    cart[id] = (cart[id] || 0) + 1;
    refreshCart();
    renderMenu();
    renderFavorites();
    renderRecommendedPanel();
    renderPopularPanel();
    showToast('Dodano u košaricu!');
  }

  function changeQty(id, delta) {
    cart[id] = (cart[id] || 0) + delta;
    if (cart[id] <= 0) delete cart[id];
    refreshCart();
    renderMenu();
    renderFavorites();
    renderRecommendedPanel();
    renderPopularPanel();
  }

  function clearCart() {
    cart = {};
    refreshCart();
    renderMenu();
    renderFavorites();
    renderRecommendedPanel();
    renderPopularPanel();
    refreshOrderGateUi();
  }

  function updateItemCard() {
    renderMenu();
    renderFavorites();
  }

  function closeMiniCart() {
    const pop = document.getElementById('mini-cart-popover');
    if (!pop) return;
    pop.style.display = 'none';
  }

  function toggleMiniCart(event) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }
    const pop = document.getElementById('mini-cart-popover');
    if (!pop) return;
    const visible = pop.style.display !== 'none';
    pop.style.display = visible ? 'none' : 'grid';
  }

  function openCartWidgetFromMiniCart() {
    closeMiniCart();
    const card = document.getElementById('cart-panel');
    if (card && typeof card.scrollIntoView === 'function') {
      card.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }

  function refreshTopCartWidget(totalAmount, itemCount) {
    const badge = document.getElementById('top-cart-badge');
    const total = document.getElementById('top-cart-total');
    const miniTotal = document.getElementById('mini-cart-total');
    if (badge) badge.textContent = String(itemCount);
    if (total) total.textContent = fmt(totalAmount);
    if (miniTotal) miniTotal.textContent = fmt(totalAmount);
  }

  function renderMiniCart(ids, totalAmount) {
    const miniItems = document.getElementById('mini-cart-items');
    if (!miniItems) return;
    if (ids.length === 0) {
      miniItems.innerHTML = '<p class="mini-cart-empty">Košarica je prazna.</p>';
      refreshTopCartWidget(0, 0);
      return;
    }

    const itemCount = ids.reduce((sum, id) => sum + Number(cart[id] || 0), 0);
    miniItems.innerHTML = ids.map(id => {
      const item = menuItems.find(i => i.id === id);
      if (!item) return '';
      const qty = Number(cart[id] || 0);
      return `
        <div class="mini-cart-line">
          <div>
            <div class="mini-cart-name">${escapeHtml(item.name)}</div>
            <div class="mini-cart-price">${fmt(item.price)} x ${qty}</div>
          </div>
          <div class="qty-ctrl">
            <button class="qty-btn" onclick="changeQty(${id}, -1)">-</button>
            <span class="qty-val">${qty}</span>
            <button class="qty-btn" onclick="changeQty(${id}, +1)">+</button>
          </div>
        </div>`;
    }).join('');
    refreshTopCartWidget(totalAmount, itemCount);
  }

  function refreshCart() {
    const container = document.getElementById('cart-items');
    const ids = Object.keys(cart).map(Number);
    refreshOrderGateUi();
    if (!container) return;

    if (ids.length === 0) {
      container.innerHTML = '<p class="cart-empty">Košarica je prazna.</p>';
      const totalEl = document.getElementById('cart-total');
      if (totalEl) totalEl.textContent = '0,00 €';
      renderMiniCart([], 0);
      return;
    }

    let total = 0;
    container.innerHTML = ids.map(id => {
      const item = menuItems.find(i => i.id === id);
      if (!item) return '';
      const qty = Number(cart[id] || 0);
      const lineTotal = item.price * qty;
      total += lineTotal;
      return `
        <div class="cart-item">
          <div class="cart-item-info">
            <div class="cart-item-name">${escapeHtml(item.name)}</div>
            <div class="cart-item-price">${fmt(item.price)} x ${qty} = ${fmt(lineTotal)}</div>
          </div>
          <div class="qty-ctrl">
            <button class="qty-btn" onclick="changeQty(${id}, -1)">-</button>
            <span class="qty-val">${qty}</span>
            <button class="qty-btn" onclick="changeQty(${id}, +1)">+</button>
          </div>
        </div>`;
    }).join('');

    const totalEl = document.getElementById('cart-total');
    if (totalEl) totalEl.textContent = fmt(total);
    renderMiniCart(ids, total);
    refreshOrderGateUi();
  }
  async function placeOrder() {
    const ids = Object.keys(cart).map(Number);
    const blockReason = getOrderBlockReason();
    if (blockReason) { showToast(blockReason); return; }
    if (ids.length === 0) { showToast('Košarica je prazna!'); return; }
    const pickup = document.getElementById('pickup-input').value;
    if (!pickup) { showToast('Odaberite vrijeme preuzimanja!'); return; }
    const notes = document.getElementById('notes-input').value.trim() || null;
    const items = ids.map(id => ({ menu_item_id: id, quantity: cart[id] }));
    const organizationId = isStudentRole()
      ? selectedOrganizationId
      : getActiveStaffOrganizationId();
    if (!organizationId) { showToast('Odaberite restoran prije narudžbe.'); return; }
    try {
      const res = await fetch('/orders/', {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ pickup_time: new Date(pickup).toISOString(), notes, items, organization_id: organizationId }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        showToast('Greška: ' + (err.detail || 'Pokušajte ponovno'));
        return;
      }
      clearCart();
      document.getElementById('notes-input').value = '';
      document.getElementById('pickup-input').value = minPickupTime();
      showToast('Narudžba uspješno kreirana!');
      await loadDashboardOrders();
      if (document.getElementById('orders-section').style.display !== 'none') loadOrders();
    } catch {
      showToast('Greška pri slanju narudžbe');
    }
  }

  //  MY ORDERS 

  async function loadOrders() {
    const container = document.getElementById('orders-container');
    container.innerHTML = '<div class="spinner"></div>';
    
    // Admin/staff see orders for their restaurant, students see only their own
    let orders;
    if (isStaffRole()) {
      const res = await fetch('/orders/all', { headers: authHeaders() });
      if (!res.ok) { container.innerHTML = '<p class="cart-empty">Greška pri učitavanju.</p>'; return; }
      orders = await res.json();
    } else {
      const res = await fetch('/orders/my', { headers: authHeaders() });
      if (!res.ok) { container.innerHTML = '<p class="cart-empty">Greška pri učitavanju.</p>'; return; }
      orders = await res.json();
    }
    
    personalOrders = Array.isArray(orders) ? [...orders] : [];
    renderRecommendedPanel();
    renderPopularPanel();
    renderNutritionPanel();
    renderExperienceWidget();
    if (orders.length === 0) {
      const emptyMsg = isStaffRole() 
        ? 'Nema narudžbi za vaš restoran.' 
        : 'Nema narudžbi.';
      container.innerHTML = `<p style="color:var(--muted);text-align:center;padding:2.5rem">${emptyMsg}</p>`;
      return;
    }
    orders.sort((a,b) => new Date(b.created_at) - new Date(a.created_at));
    container.innerHTML = orders.map(o => renderOrderCard(o)).join('');
  }

  function renderOrderCard(o) {
    const d = new Date(o.pickup_time);
    const pickupStr = d.toLocaleDateString('hr-HR') + ' ' + d.toLocaleTimeString('hr-HR', { hour: '2-digit', minute: '2-digit' });
    const statusLabels = { pending: 'Na čekanju', confirmed: 'Potvrđeno', ready: 'Spremno', completed: 'Završeno', cancelled: 'Otkazano' };
    const itemList = o.items.map(i => `${i.menu_item_name || 'Artikl #' + i.menu_item_id} ×${i.quantity}`).join(', ');
    return `
      <div class="order-card">
        <div class="order-header">
          <span class="order-id">Narudžba #${o.id}</span>
          <span class="status-badge status-${o.status}">${statusLabels[o.status] || o.status}</span>
        </div>
        <div class="order-items-list">${itemList}</div>
        <div class="order-total">Ukupno: ${fmt(o.total_price)}</div>
        <div class="order-pickup">Preuzimanje: ${pickupStr}</div>
        ${o.notes ? `<div style="font-size:.8rem;color:var(--muted);margin-top:.3rem">Napomena: ${o.notes}</div>` : ''}
        ${(() => {
          const active = ['pending', 'confirmed', 'ready'].includes(o.status);
          if (isStaffRole() && active) return `
            <div style="display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.75rem">
              <button class="btn btn-primary btn-sm" onclick="updateOrderStatus(${o.id},'completed',this)">Zaključi narudžbu</button>
              ${o.status === 'pending' ? `<button class="btn btn-ghost btn-sm" onclick="updateOrderStatus(${o.id},'confirmed',this)">Potvrdi</button>` : ''}
              ${o.status === 'confirmed' ? `<button class="btn btn-ghost btn-sm" onclick="updateOrderStatus(${o.id},'ready',this)">Označi kao spremno</button>` : ''}
              <button class="btn btn-danger btn-sm" onclick="cancelOrder(${o.id},this)">Otkaži</button>
            </div>`;
          if (!isStaffRole() && o.status === 'pending') return `<button class="btn btn-danger btn-sm" style="margin-top:.75rem" onclick="cancelOrder(${o.id},this)">Otkaži narudžbu</button>`;
          return '';
        })()}
      </div>`;
  }

  async function updateOrderStatus(id, newStatus, btn) {
    btn.disabled = true;
    const res = await fetch('/orders/' + id + '/status', {
      method: 'PATCH',
      headers: { ...authHeaders(), 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: newStatus }),
    });
    if (res.ok) {
      const labels = { confirmed: 'Potvrđeno.', ready: 'Označeno kao spremno.', completed: 'Narudžba zaključena.' };
      showToast(labels[newStatus] || 'Status ažuriran.');
      await loadOrders();
    } else {
      showToast('Nije moguće ažurirati status narudžbe.');
      btn.disabled = false;
    }
  }

  async function cancelOrder(id, btn) {
    btn.disabled = true;
    const res = await fetch('/orders/' + id, { method: 'DELETE', headers: authHeaders() });
    if (res.ok || res.status === 204) {
      showToast('Narudžba otkazana.');
      await loadDashboardOrders();
      loadOrders();
    } else {
      showToast('Nije moguće otkazati narudžbu.');
      btn.disabled = false;
    }
  }

  //  TABS 

  async function loadDashboardOrders() {
    try {
      const personalRes = await fetch('/orders/my', { headers: authHeaders() });
      if (personalRes.ok) {
        personalOrders = await personalRes.json();
      } else {
        personalOrders = [];
      }
    } catch {
      personalOrders = [];
    }

    globalOrders = [];
    popularItemStats = [];
    try {
      const params = new URLSearchParams({ limit: '12' });
      const orgIdForPopularity = isStudentRole()
        ? selectedOrganizationId
        : getActiveStaffOrganizationId();
      if (orgIdForPopularity) {
        params.set('organization_id', String(orgIdForPopularity));
      }
      const popularRes = await fetch('/orders/popular?' + params.toString(), { headers: authHeaders() });
      if (popularRes.ok) {
        popularItemStats = await popularRes.json();
      }
    } catch {
      popularItemStats = [];
    }
    recommendedCarouselIndex = 0;

    renderRecommendedPanel();
    renderPopularPanel();
    renderNutritionPanel();
    renderExperienceWidget();
  }

  function getItemsByPriority(ids, fallbackLimit = 4, includeFallback = true) {
    const picked = [];
    ids.forEach(id => {
      const item = getItemById(id);
      if (item && !picked.some(existing => Number(existing.id) === Number(item.id))) {
        picked.push(item);
      }
    });
    if (picked.length >= fallbackLimit) return picked.slice(0, fallbackLimit);
    if (!includeFallback) return picked.slice(0, fallbackLimit);

    const fallback = menuItems
      .filter(item => !picked.some(existing => Number(existing.id) === Number(item.id)))
      .sort((a, b) => a.name.localeCompare(b.name));
    return [...picked, ...fallback].slice(0, fallbackLimit);
  }

  function shiftRecommendedSlide(direction) {
    const groupSize = window.matchMedia('(max-width: 640px)').matches ? 1 : 2;
    const picks = getItemsByPriority(getPersonalizedItemIds(), 4, false).slice(0, 4);
    if (!picks.length) {
      recommendedCarouselIndex = 0;
      return;
    }
    const slideCount = Math.max(1, Math.ceil(picks.length / groupSize));
    recommendedCarouselIndex = (recommendedCarouselIndex + direction + slideCount) % slideCount;
    renderRecommendedPanel();
  }

  function renderRecommendedPanel() {
    const wrap = document.getElementById('recommended-items');
    if (!wrap) return;

    const personalizedIds = getPersonalizedItemIds();
    const picks = getItemsByPriority(personalizedIds, 4, false).slice(0, 4);

    if (!picks.length) {
      wrap.innerHTML = '<p class="dashboard-empty-note">Nema dovoljno osobnih podataka za preporuke. Dodajte favorite ili napravite narudžbu.</p>';
      return;
    }

    const groupSize = window.matchMedia('(max-width: 640px)').matches ? 1 : 2;
    const slideCount = Math.max(1, Math.ceil(picks.length / groupSize));
    if (recommendedCarouselIndex >= slideCount) recommendedCarouselIndex = 0;
    const start = recommendedCarouselIndex * groupSize;
    const visible = picks.slice(start, start + groupSize);

    wrap.innerHTML = `
      <div class="recommended-carousel">
        <button type="button" class="recommended-nav-btn" onclick="shiftRecommendedSlide(-1)" ${slideCount > 1 ? '' : 'disabled'} aria-label="Prethodna preporuka">&#8249;</button>
        <div class="recommended-carousel-track">
          ${visible.map(item => `
            <article class="recommended-item">
              <div class="recommended-item-img">
                <img src="${itemImageSrc(item)}" alt="${escapeHtml(item.name)}" onerror="this.src='${FALLBACK_IMAGE}'" />
              </div>
              <div class="recommended-item-name">${escapeHtml(item.name)}</div>
              <div class="item-price-row">
                <span class="recommended-item-price">${fmt(item.price)}</span>
                <button type="button" title="Dodaj u košaricu" onclick="addToCart(${item.id})">+</button>
              </div>
            </article>
          `).join('')}
        </div>
        <button type="button" class="recommended-nav-btn" onclick="shiftRecommendedSlide(1)" ${slideCount > 1 ? '' : 'disabled'} aria-label="Sljedeća preporuka">&#8250;</button>
      </div>
      <div class="recommended-carousel-footer">Slide ${recommendedCarouselIndex + 1}/${slideCount}</div>
    `;
  }

  function renderPopularPanel() {
    const wrap = document.getElementById('popular-items');
    if (!wrap) return;

    const picks = getItemsByPriority(getPopularItemIds(), 4, false);
    if (!picks.length) {
      wrap.innerHTML = '<p class="dashboard-empty-note">Nema dovoljno podataka za popularna jela.</p>';
      return;
    }

    wrap.innerHTML = picks.map(item => {
      const stats = popularItemStats.find(row => Number(row.menu_item_id) === Number(item.id));
      const count = stats ? Number(stats.order_count || 0) : 0;
      return `
      <article class="recommended-item">
        <div class="recommended-item-img">
          <img src="${itemImageSrc(item)}" alt="${escapeHtml(item.name)}" onerror="this.src='${FALLBACK_IMAGE}'" />
        </div>
        <div class="recommended-item-name">${escapeHtml(item.name)}</div>
        <div class="recommended-item-price">${fmt(item.price)}</div>
        <div class="helper-note tight">Narudžbi: ${count}</div>
        <button type="button" title="Dodaj u košaricu" onclick="addToCart(${item.id})">+</button>
      </article>
      `;
    }).join('');
  }

  function renderNutritionPanel() {
    const chart = document.getElementById('nutrition-chart');
    const spendEl = document.getElementById('nutrition-spend');
    const countEl = document.getElementById('nutrition-count');
    const rangeEl = document.getElementById('nutrition-range');
    if (!chart || !spendEl || !countEl || !rangeEl) return;

    const range = rangeEl.value === 'month' ? 'month' : 'week';
    const now = new Date();
    let labels = [];
    let buckets = [];

    if (range === 'month') {
      const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
      const monthEnd = new Date(now.getFullYear(), now.getMonth() + 1, 0);
      monthEnd.setHours(23, 59, 59, 999);
      const weekCount = Math.max(1, Math.ceil(monthEnd.getDate() / 7));
      labels = Array.from({ length: weekCount }, (_, index) => `TJ ${index + 1}`);
      buckets = labels.map(() => ({ spend: 0, orders: 0 }));

      personalOrders.forEach(order => {
        const created = new Date(order.created_at || order.pickup_time);
        if (Number.isNaN(created.getTime())) return;
        if (created < monthStart || created > monthEnd) return;
        const dayInMonth = created.getDate();
        const idx = Math.min(weekCount - 1, Math.floor((dayInMonth - 1) / 7));
        buckets[idx].spend += Number(order.total_price || 0);
        buckets[idx].orders += 1;
      });
    } else {
      const start = new Date(now);
      const day = (now.getDay() + 6) % 7;
      start.setDate(now.getDate() - day);
      start.setHours(0, 0, 0, 0);
      labels = ['PON', 'UTO', 'SRI', 'ČET', 'PET', 'SUB', 'NED'];
      buckets = labels.map(() => ({ spend: 0, orders: 0 }));

      personalOrders.forEach(order => {
        const created = new Date(order.created_at || order.pickup_time);
        if (Number.isNaN(created.getTime()) || created < start) return;
        const idx = (created.getDay() + 6) % 7;
        buckets[idx].spend += Number(order.total_price || 0);
        buckets[idx].orders += 1;
      });
    }

    const totalSpend = buckets.reduce((sum, bucket) => sum + bucket.spend, 0);
    const totalOrders = buckets.reduce((sum, bucket) => sum + bucket.orders, 0);
    spendEl.textContent = fmt(totalSpend);
    countEl.textContent = String(totalOrders);

    const maxSpend = Math.max(...buckets.map(bucket => bucket.spend), 1);
    chart.innerHTML = buckets.map((bucket, idx) => {
      const height = Math.max(10, Math.round((bucket.spend / maxSpend) * 118));
      return `
        <div class="nutrition-bar-col" title="${labels[idx]}: ${fmt(bucket.spend)}">
          <div class="nutrition-bar" style="height:${height}px"></div>
          <span class="nutrition-day">${labels[idx]}</span>
        </div>
      `;
    }).join('');
  }

  function setRatingValue(value) {
    if (selectedRatingItemId && userMealRatings[String(selectedRatingItemId)]) return;
    pendingRatingValue = Math.max(1, Math.min(5, Number(value) || 1));
    renderExperienceWidget();
  }

  function chooseExperienceItem(itemId) {
    selectedRatingItemId = Number(itemId);
    renderExperienceWidget();
  }

  function shiftExperienceSlide(direction) {
    if (!experienceCarouselItems.length) return;
    const length = experienceCarouselItems.length;
    const currentIndex = experienceCarouselItems.findIndex(item =>
      Number(item.menu_item_id) === Number(selectedRatingItemId)
    );
    const safeIndex = currentIndex >= 0 ? currentIndex : 0;
    const nextIndex = (safeIndex + Number(direction || 0) + length) % length;
    selectedRatingItemId = Number(experienceCarouselItems[nextIndex].menu_item_id);
    renderExperienceWidget();
  }

  function onExperienceTouchStart(event) {
    const touch = event && event.touches ? event.touches[0] : null;
    experienceTouchStartX = touch ? Number(touch.clientX || 0) : null;
  }

  function onExperienceTouchEnd(event) {
    if (experienceTouchStartX == null) return;
    const touch = event && event.changedTouches ? event.changedTouches[0] : null;
    const endX = touch ? Number(touch.clientX || 0) : null;
    if (endX == null) {
      experienceTouchStartX = null;
      return;
    }
    const delta = endX - experienceTouchStartX;
    experienceTouchStartX = null;
    if (Math.abs(delta) < 42) return;
    shiftExperienceSlide(delta < 0 ? 1 : -1);
  }

  function renderExperienceWidget() {
    const listEl = document.getElementById('experience-last-order-list');
    const starsEl = document.getElementById('experience-stars');
    const noteEl = document.getElementById('experience-rating-note');
    const submitBtn = document.getElementById('experience-submit-btn');
    if (!listEl || !starsEl || !noteEl || !submitBtn) return;

    if (!personalOrders.length) {
      experienceCarouselItems = [];
      selectedRatingItemId = null;
      listEl.innerHTML = '<p class="experience-empty">Nakon prve narudžbe ovdje možete ocijeniti jela.</p>';
      starsEl.innerHTML = '';
      noteEl.textContent = '';
      submitBtn.disabled = true;
      submitBtn.textContent = 'Ocijeni';
      return;
    }

    const latest = [...personalOrders].sort((a, b) => new Date(b.created_at) - new Date(a.created_at))[0];
    const latestItems = [];
    (latest.items || []).forEach(item => {
      const itemId = Number(item.menu_item_id);
      if (!latestItems.some(existing => Number(existing.menu_item_id) === itemId)) {
        latestItems.push(item);
      }
    });

    if (!latestItems.length) {
      experienceCarouselItems = [];
      selectedRatingItemId = null;
      listEl.innerHTML = '<p class="experience-empty">Zadnja narudžba nema stavki za ocjenjivanje.</p>';
      starsEl.innerHTML = '';
      noteEl.textContent = '';
      submitBtn.disabled = true;
      submitBtn.textContent = 'Ocijeni';
      return;
    }

    experienceCarouselItems = latestItems;
    if (!selectedRatingItemId || !experienceCarouselItems.some(item => Number(item.menu_item_id) === Number(selectedRatingItemId))) {
      selectedRatingItemId = Number(experienceCarouselItems[0].menu_item_id);
    }

    const activeIndex = Math.max(
      0,
      experienceCarouselItems.findIndex(item => Number(item.menu_item_id) === Number(selectedRatingItemId))
    );
    const activeItem = experienceCarouselItems[activeIndex];
    const activeMenuItem = getItemById(activeItem.menu_item_id);
    const existingRating = Number(userMealRatings[String(selectedRatingItemId)] || 0);
    const dateText = fmtDateShort(latest.created_at || latest.pickup_time);
    const slideTitle = escapeHtml(
      activeItem.menu_item_name || (activeMenuItem ? activeMenuItem.name : `Artikal #${activeItem.menu_item_id}`)
    );
    const slideAlt = escapeHtml(activeItem.menu_item_name || 'Jelo');
    const hasMultiple = experienceCarouselItems.length > 1;
    listEl.innerHTML = `
      <div class="experience-carousel" ${hasMultiple ? 'ontouchstart="onExperienceTouchStart(event)" ontouchend="onExperienceTouchEnd(event)"' : ''}>
        <button type="button" class="experience-nav-btn" onclick="shiftExperienceSlide(-1)" ${hasMultiple ? '' : 'disabled'} aria-label="Prethodno jelo">&#8249;</button>
        <article class="experience-slide ${existingRating > 0 ? 'rated' : ''}">
          <span class="experience-slide-thumb">
            <img src="${itemImageSrc(activeMenuItem || {})}" alt="${slideAlt}" onerror="this.src='${FALLBACK_IMAGE}'" />
          </span>
          <span class="experience-slide-main">
            <strong>${slideTitle}</strong>
            <span>${dateText}</span>
          </span>
          <span class="experience-slide-counter">${activeIndex + 1}/${experienceCarouselItems.length}</span>
        </article>
        <button type="button" class="experience-nav-btn" onclick="shiftExperienceSlide(1)" ${hasMultiple ? '' : 'disabled'} aria-label="Sljedeće jelo">&#8250;</button>
      </div>
    `;

    const effectiveRating = existingRating > 0 ? existingRating : pendingRatingValue;
    starsEl.innerHTML = [1, 2, 3, 4, 5].map(value => `
      <button type="button" class="experience-star ${value <= effectiveRating ? 'active' : ''}" onclick="setRatingValue(${value})" ${existingRating > 0 ? 'disabled' : ''}>&#9733;</button>
    `).join('');

    if (existingRating > 0) {
      noteEl.textContent = `Već ste ocijenili ovo jelo ocjenom ${existingRating}/5.`;
      submitBtn.disabled = true;
      submitBtn.textContent = 'Ocijenjeno';
    } else {
      noteEl.textContent = 'Jedno jelo možete ocijeniti samo jednom.';
      submitBtn.disabled = false;
      submitBtn.textContent = 'Ocijeni';
    }
  }

  async function submitExperienceRating() {
    if (!selectedRatingItemId) {
      showToast('Odaberite jelo koje želite ocijeniti.');
      return;
    }
    if (userMealRatings[String(selectedRatingItemId)]) {
      showToast('Ovo jelo ste već ocijenili.');
      return;
    }

    const res = await fetch('/ratings/', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({
        menu_item_id: Number(selectedRatingItemId),
        rating: Number(pendingRatingValue || 0),
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      showToast(err.detail || 'Spremanje ocjene nije uspjelo.');
      return;
    }

    await loadRatingsData();
    renderMenu();
    renderFavorites();
    renderRecommendedPanel();
    renderPopularPanel();
    renderExperienceWidget();
    showToast('Hvala! Ocjena je spremljena.');
  }

  async function showTab(tab, options = {}) {
    const resolvedTab = normalizeTabForCurrentUser(tab);
    const updateHash = options.updateHash !== false;
    activeView = resolvedTab;
    if (updateHash) {
      writeTabToHash(resolvedTab);
    }
    const menuVisible = resolvedTab === 'home' || resolvedTab === 'menu';

    document.getElementById('menu-section').style.display = menuVisible ? '' : 'none';
    document.getElementById('favorites-section').style.display = resolvedTab === 'favorites' ? '' : 'none';
    document.getElementById('orders-section').style.display = resolvedTab === 'orders' ? '' : 'none';
    document.getElementById('admin-section').style.display = resolvedTab === 'admin' ? '' : 'none';
    document.getElementById('users-section').style.display = resolvedTab === 'users' ? '' : 'none';
    document.getElementById('profile-section').style.display = resolvedTab === 'profile' ? '' : 'none';

    setTabLinkState('tab-home', resolvedTab === 'home');
    setTabLinkState('tab-menu', resolvedTab === 'menu');
    setTabLinkState('tab-orders', resolvedTab === 'orders');
    setTabLinkState('tab-favorites', resolvedTab === 'favorites');
    setTabLinkState('tab-admin', resolvedTab === 'admin');
    setTabLinkState('tab-users', resolvedTab === 'users');
    setTabLinkState('tab-profile', resolvedTab === 'profile');

    const hero = document.getElementById('hero-shell');
    const dashboard = document.getElementById('menu-bottom-grid');
    if (hero) hero.style.display = resolvedTab === 'home' ? '' : 'none';
    if (dashboard) dashboard.style.display = resolvedTab === 'home' ? '' : 'none';

    if (resolvedTab === 'home' || resolvedTab === 'menu') {
      buildSidebar();
      renderMenu();
    }
    if (resolvedTab === 'favorites') renderFavorites();
    if (resolvedTab === 'orders') await loadOrders();
    if (resolvedTab === 'admin') {
      renderStaffOrganizationSelector();
      await loadAdminItems();
    }
    if (resolvedTab === 'users') {
      renderStaffOrganizationSelector();
      await loadOrganizationUsers();
      if (isOwnerRole()) await loadOwnerAdmins();
    }
    if (resolvedTab === 'profile') {
      const isspSection = document.getElementById('issp-section');
      if (isspSection) {
        if (!isStudentRole()) {
          isspSection.style.display = 'none';
        } else {
          isspSection.style.display = '';
          const disabledMsg = document.getElementById('issp-disabled-msg');
          const enabledContent = document.getElementById('issp-enabled-content');
          if (disabledMsg) disabledMsg.style.display = isspEnabled ? 'none' : 'block';
          if (enabledContent) enabledContent.style.display = '';
          setISSPLinkMode(isspLinkMode);
          if (isspProfileData) {
            renderISSPResult(isspProfileData);
          }
        }
      }
      await renderProfilePage();
    }

    if (isMobileLayout()) {
      closeMobileSidebar();
    }
    refreshStudentSelectorUi();
  }
  async function loadAdminItems() {
    const container = document.getElementById('admin-items-container');
    container.innerHTML = '<div class="spinner"></div>';
    const params = new URLSearchParams({ available_only: 'false' });
    const activeOrgId = getActiveStaffOrganizationId();
    if (activeOrgId) params.set('organization_id', String(activeOrgId));
    const res = await fetch('/menu/items?' + params.toString(), { headers: authHeaders() });
    if (!res.ok) { container.innerHTML = '<p class="error-msg" style="padding:1rem">Greška pri učitavanju.</p>'; return; }
    adminAllItems = await res.json();
    renderAdminItems();
  }

  function renderAdminItems() {
    const container = document.getElementById('admin-items-container');
    if (adminAllItems.length === 0) {
      container.innerHTML = '<p style="color:var(--muted);text-align:center;padding:2.5rem">Nema artikala. Dodajte prvi!</p>';
      return;
    }
    const sorted = [...adminAllItems].sort((a,b) => a.category.localeCompare(b.category) || a.name.localeCompare(b.name));
    container.innerHTML = `
      <div class="table-scroll">
      <table class="admin-table">
        <thead>
          <tr>
            <th>Šifra</th><th>Slika</th><th>Naziv</th><th>Kategorija</th><th>Cijena</th><th>Status</th><th>Akcije</th>
          </tr>
        </thead>
        <tbody>
          ${sorted.map(item => `
            <tr>
              <td style="color:var(--muted);font-size:.8rem;font-weight:700">${item.code}</td>
              <td><img class="admin-thumb" src="${itemImageSrc(item)}" alt="${item.name}" onerror="this.src='${FALLBACK_IMAGE}'" /></td>
              <td>
                <div style="font-weight:700">${item.name}</div>
                ${item.description ? `<div style="font-size:.75rem;color:var(--muted)">${item.description}</div>` : ''}
              </td>
              <td style="color:var(--muted)">${item.category}</td>
              <td style="font-weight:900;color:var(--danger)">${fmt(item.price)}</td>
              <td>
                <button
                  type="button"
                  class="availability-toggle ${item.is_available ? 'on' : 'off'}"
                  onclick="toggleMenuItemAvailability(${item.id}, ${item.is_available ? 'false' : 'true'})"
                  title="${item.is_available ? 'Oznaci kao nedostupno' : 'Oznaci kao dostupno'}"
                >
                  <span class="availability-switch" aria-hidden="true"></span>
                  <span class="availability-label">${item.is_available ? 'Dostupno' : 'Nedostupno'}</span>
                </button>
              </td>
              <td>
                <div style="display:flex;gap:.4rem">
                  <button class="btn btn-dark btn-sm" onclick="adminEdit(${item.id})">Uredi</button>
                  <button class="btn btn-danger btn-sm" onclick="adminDelete(${item.id}, this)">Obriši</button>
                </div>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
      </div>`;
  }

  async function toggleMenuItemAvailability(itemId, nextAvailability) {
    const nextValue = nextAvailability === true || nextAvailability === 'true';
    const index = adminAllItems.findIndex(item => Number(item.id) === Number(itemId));
    if (index === -1) return;
    const previousValue = !!adminAllItems[index].is_available;
    adminAllItems[index] = { ...adminAllItems[index], is_available: nextValue };
    renderAdminItems();

    try {
      const res = await fetch(`/menu/items/${itemId}`, {
        method: 'PUT',
        headers: authHeaders(),
        body: JSON.stringify({ is_available: nextValue }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        adminAllItems[index] = { ...adminAllItems[index], is_available: previousValue };
        renderAdminItems();
        showToast(err.detail || 'Neuspjela promjena dostupnosti artikla.');
        return;
      }
      const savedItem = await res.json();
      adminAllItems[index] = { ...adminAllItems[index], ...savedItem };
      renderAdminItems();
      await loadMenu();
    } catch {
      adminAllItems[index] = { ...adminAllItems[index], is_available: previousValue };
      renderAdminItems();
      showToast('Greška pri spremanju dostupnosti artikla.');
    }
  }

  function openAdminForm(mode, item = null) {
    adminEditId = item ? item.id : null;
    document.getElementById('admin-form-title').textContent = item ? 'Uredi artikal' : 'Novi artikal';
    document.getElementById('admin-form-submit').textContent = item ? 'Spremi izmjene' : 'Spremi';
    document.getElementById('admin-form-error').textContent = '';
    document.getElementById('af-code').value     = item ? item.code : '';
    document.getElementById('af-group').value    = item ? item.group_code : '';
    document.getElementById('af-name').value     = item ? item.name : '';
    document.getElementById('af-desc').value     = item ? (item.description || '') : '';
    document.getElementById('af-price').value    = item ? item.price : '';
    document.getElementById('af-category').value = item ? item.category : 'Ostalo';
    document.getElementById('af-unit').value     = item ? item.unit : 'KOM';
    document.getElementById('af-available').checked = item ? item.is_available : true;
    document.getElementById('af-kcal').value    = item && item.calories_kcal != null ? item.calories_kcal : '';
    document.getElementById('af-protein').value = item && item.protein_g != null ? item.protein_g : '';
    document.getElementById('af-carbs').value   = item && item.carbs_g != null ? item.carbs_g : '';
    document.getElementById('af-fat').value     = item && item.fat_g != null ? item.fat_g : '';
    document.getElementById('af-image').value = '';
    adminOriginalImageUrl = itemImageSrc(item);
    setAdminImagePreview(adminOriginalImageUrl, !!(item && item.image_url));
    const wrap = document.getElementById('admin-form-wrap');
    wrap.style.display = '';
    wrap.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function closeAdminForm() {
    document.getElementById('admin-form-wrap').style.display = 'none';
    adminEditId = null;
    adminOriginalImageUrl = FALLBACK_IMAGE;
  }

  async function submitAdminForm() {
    const errEl = document.getElementById('admin-form-error');
    errEl.textContent = '';
    const code       = parseInt(document.getElementById('af-code').value);
    const group_code = parseInt(document.getElementById('af-group').value);
    const name       = document.getElementById('af-name').value.trim();
    const price      = parseFloat(document.getElementById('af-price').value);

    if (!name || isNaN(code) || isNaN(group_code) || isNaN(price)) {
      errEl.textContent = 'Ispunite sva obavezna polja (*) ispravno.';
      return;
    }
    if (price < 0) { errEl.textContent = 'Cijena ne može biti negativna.'; return; }
    const imageInput = document.getElementById('af-image');
    const imageFile = imageInput.files && imageInput.files[0] ? imageInput.files[0] : null;
    if (imageFile) {
      const allowed = ['image/jpeg', 'image/png', 'image/webp'];
      if (!allowed.includes(imageFile.type)) {
        errEl.textContent = 'Slika mora biti JPEG, PNG ili WEBP format.';
        return;
      }
      if (imageFile.size > 3 * 1024 * 1024) {
        errEl.textContent = 'Maksimalna veličina slike je 3MB.';
        return;
      }
    }

    const activeOrgId = getActiveStaffOrganizationId();

    const payload = {
      code, group_code, name,
      description:  document.getElementById('af-desc').value.trim() || null,
      price,
      category:     document.getElementById('af-category').value.trim() || 'Ostalo',
      unit:         document.getElementById('af-unit').value.trim() || 'KOM',
      is_available: document.getElementById('af-available').checked,
      calories_kcal: parseOptFloat(document.getElementById('af-kcal').value),
      protein_g:     parseOptFloat(document.getElementById('af-protein').value),
      carbs_g:       parseOptFloat(document.getElementById('af-carbs').value),
      fat_g:         parseOptFloat(document.getElementById('af-fat').value),
      organization_id: adminEditId ? undefined : activeOrgId,
    };

    const url    = adminEditId ? `/menu/items/${adminEditId}` : '/menu/items';
    const method = adminEditId ? 'PUT' : 'POST';
    try {
      const res = await fetch(url, { method, headers: authHeaders(), body: JSON.stringify(payload) });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        errEl.textContent = err.detail || 'Greška pri spremanju';
        return;
      }
      const savedItem = await res.json();
      if (imageFile) {
        const formData = new FormData();
        formData.append('file', imageFile);
        const uploadRes = await fetch(`/menu/items/${savedItem.id}/image`, {
          method: 'POST',
          headers: { 'Authorization': 'Bearer ' + token },
          body: formData,
        });
        if (!uploadRes.ok) {
          const uploadErr = await uploadRes.json().catch(() => ({}));
          errEl.textContent = uploadErr.detail || 'Artikal je spremljen, ali upload slike nije uspio.';
          return;
        }
      }
      closeAdminForm();
      showToast(adminEditId ? 'Artikal ažuriran!' : 'Artikal dodan!');
      await loadAdminItems();
      await loadMenu();
    } catch {
      errEl.textContent = 'Greška pri spajanju';
    }
  }

  async function removeAdminImage(event) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
    }
    const errEl = document.getElementById('admin-form-error');
    errEl.textContent = '';
    const imageInput = document.getElementById('af-image');
    if (imageInput.files && imageInput.files[0]) {
      imageInput.value = '';
      setAdminImagePreview(adminOriginalImageUrl || FALLBACK_IMAGE, !!(adminOriginalImageUrl && adminOriginalImageUrl !== FALLBACK_IMAGE));
      return;
    }
    if (!adminEditId) {
      errEl.textContent = 'Sliku je moguće ukloniti samo kod postojećeg artikla.';
      return;
    }
    const res = await fetch(`/menu/items/${adminEditId}/image`, {
      method: 'DELETE',
      headers: authHeaders(),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      errEl.textContent = err.detail || 'Greška pri uklanjanju slike.';
      return;
    }
    adminOriginalImageUrl = FALLBACK_IMAGE;
    setAdminImagePreview(FALLBACK_IMAGE, false);
    showToast('Slika je uklonjena.');
    await loadAdminItems();
    await loadMenu();
  }

  function adminEdit(id) {
    const item = adminAllItems.find(i => i.id === id);
    if (item) openAdminForm('edit', item);
  }

  async function adminDelete(id, btn) {
    if (!confirm('Jeste li sigurni da želite trajno obrisati ovaj artikal?')) return;
    btn.disabled = true;
    const res = await fetch(`/menu/items/${id}`, { method: 'DELETE', headers: authHeaders() });
    if (res.ok || res.status === 204) {
      showToast('Artikal obrisan.');
      await loadAdminItems();
      await loadMenu();
    } else {
      showToast('Greška pri brisanju.');
      btn.disabled = false;
    }
  }

  async function loadOrganizationUsers() {
    if (!isStaffRole()) return;
    const listEl = document.getElementById('org-users-list');
    const contextEl = document.getElementById('org-context');
    listEl.innerHTML = '<div class="spinner"></div>';
    contextEl.innerHTML = '<div class="spinner"></div>';

    const params = new URLSearchParams();
    const activeOrgId = getActiveStaffOrganizationId();
    if (activeOrgId) params.set('organization_id', String(activeOrgId));
    const url = params.toString() ? `/auth/users?${params.toString()}` : '/auth/users';
    const res = await fetch(url, { headers: authHeaders() });
    if (!res.ok) {
      listEl.innerHTML = '<p class="error-msg">Greška pri učitavanju korisnika organizacije.</p>';
      contextEl.innerHTML = '<p class="error-msg">Nije moguće učitati organizacijski kontekst.</p>';
      return;
    }

    orgUsers = await res.json();
    renderOrganizationContext();
    renderOrganizationUsers();
    if (document.getElementById('profile-section').style.display !== 'none') {
      renderProfilePage();
    }
  }

  function renderOrganizationContext() {
    const contextEl = document.getElementById('org-context');
    const orgName = getOrganizationName(currentUser);
    const total = orgUsers.length;
    const active = orgUsers.filter(u => u.is_active).length;
    const students = orgUsers.filter(u => u.role === 'student').length;
    const staff = orgUsers.filter(u => u.role !== 'student').length;

    contextEl.innerHTML = `
      <h3 style="margin-bottom:.6rem">Organizacijski kontekst</h3>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:.8rem">
        <div><div style="font-size:.78rem;color:var(--muted)">Organizacija</div><div style="font-weight:800">${orgName}</div></div>
        <div><div style="font-size:.78rem;color:var(--muted)">Ukupno korisnika</div><div style="font-weight:800">${total}</div></div>
        <div><div style="font-size:.78rem;color:var(--muted)">Aktivni</div><div style="font-weight:800">${active}</div></div>
        <div><div style="font-size:.78rem;color:var(--muted)">Studenti / Staff</div><div style="font-weight:800">${students} / ${staff}</div></div>
      </div>`;
  }

  function renderOrganizationUsers() {
    const listEl = document.getElementById('org-users-list');
    if (!orgUsers.length) {
      listEl.innerHTML = '<p style="color:var(--muted);text-align:center;padding:2rem">Nema korisnika u organizaciji.</p>';
      return;
    }

    listEl.innerHTML = `
      <div class="table-scroll">
      <table class="admin-table">
        <thead>
          <tr><th>Email</th><th>Ime i prezime</th><th>Rola</th><th>Organizacija</th><th>Status</th></tr>
        </thead>
        <tbody>
          ${orgUsers.map(user => `
            <tr>
              <td>${user.email}</td>
              <td>${[user.first_name || '', user.last_name || ''].join(' ').trim() || '-'}</td>
              <td><span class="role-badge ${roleBadgeClass(user.role)}">${roleLabel(user.role)}</span></td>
              <td>${user.organization ? user.organization.name : '-'}</td>
              <td>
                <span class="${user.is_active ? 'avail-badge' : 'badge-unavail'}">
                  ${user.is_active ? 'Aktivan' : 'Neaktivan'}
                </span>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
      </div>`;
  }

  async function loadOwnerAdmins() {
    if (!isOwnerRole()) return;
    const listEl = document.getElementById('owner-admin-list');
    listEl.innerHTML = '<div class="spinner"></div>';
    const res = await fetch('/auth/admins', { headers: authHeaders() });
    if (!res.ok) {
      listEl.innerHTML = '<p class="error-msg">Greška pri učitavanju admin korisnika.</p>';
      return;
    }
    ownerAdmins = await res.json();
    renderOwnerAdminList();
    if (document.getElementById('profile-section').style.display !== 'none') {
      renderProfilePage();
    }
  }

  function renderOwnerAdminList() {
    const listEl = document.getElementById('owner-admin-list');
    if (!ownerAdmins.length) {
      listEl.innerHTML = '<p style="color:var(--muted)">Nema admin korisnika.</p>';
      return;
    }
    listEl.innerHTML = `
      <div class="table-scroll">
      <table class="admin-table">
        <thead>
          <tr><th>Email</th><th>Ime i prezime</th><th>Status</th><th>Akcije</th></tr>
        </thead>
        <tbody>
          ${ownerAdmins.map(admin => `
            <tr>
              <td>${admin.email}</td>
              <td>${[admin.first_name || '', admin.last_name || ''].join(' ').trim() || '-'}</td>
              <td>
                <span class="${admin.is_active ? 'avail-badge' : 'badge-unavail'}">
                  ${admin.is_active ? 'Aktivan' : 'Neaktivan'}
                </span>
              </td>
              <td>
                <div style="display:flex;gap:.4rem">
                  <button class="btn btn-dark btn-sm" onclick="ownerToggleAdmin(${admin.id}, ${admin.is_active ? 'false' : 'true'})">
                    ${admin.is_active ? 'Deaktiviraj' : 'Aktiviraj'}
                  </button>
                  <button class="btn btn-danger btn-sm" onclick="ownerDeleteAdmin(${admin.id})">Obriši</button>
                </div>
              </td>
            </tr>
          `).join('')}
        </tbody>
      </table>
      </div>`;
  }

  function renderStaffOrganizationSelector() {
    const ownerWrap = document.getElementById('org-staff-org-wrap');
    const ownerSelect = document.getElementById('org-staff-organization');
    const adminWrap = document.getElementById('admin-org-selector-wrap');
    const adminSelect = document.getElementById('admin-org-selector');
    const organizations = getStaffOrganizations();
    const activeOrgId = getActiveStaffOrganizationId();

    if (adminWrap && adminSelect) {
      if (!isStaffRole() || organizations.length === 0) {
        adminWrap.style.display = 'none';
        adminSelect.innerHTML = '';
      } else {
        adminWrap.style.display = 'inline-flex';
        adminSelect.innerHTML = organizations
          .map(org => `<option value="${Number(org.id)}" ${Number(org.id) === Number(activeOrgId) ? 'selected' : ''}>${escapeHtml(org.name || `Organizacija #${org.id}`)}</option>`)
          .join('');
        adminSelect.disabled = organizations.length <= 1;
      }
    }

    if (!ownerWrap || !ownerSelect) return;
    if (!isOwnerRole()) {
      ownerWrap.style.display = 'none';
      ownerSelect.innerHTML = '';
      return;
    }
    if (organizations.length <= 1) {
      ownerWrap.style.display = 'none';
      ownerSelect.innerHTML = organizations.length === 1
        ? `<option value="${Number(organizations[0].id)}">${escapeHtml(organizations[0].name || 'Organizacija')}</option>`
        : '';
      return;
    }
    ownerWrap.style.display = '';
    ownerSelect.innerHTML = organizations
      .map(org => `<option value="${Number(org.id)}" ${Number(org.id) === Number(activeOrgId) ? 'selected' : ''}>${escapeHtml(org.name || `Organizacija #${org.id}`)}</option>`)
      .join('');
  }

  async function onAdminOrganizationChange(value) {
    const targetId = Number(value);
    if (!targetId) return;
    await setActiveStaffOrganization(targetId, { reloadMenu: true, reloadUsers: true });
    await loadAdminItems();
  }

  async function ownerCreateAdmin() {
    const errEl = document.getElementById('org-staff-error');
    errEl.textContent = '';
    const username = document.getElementById('org-staff-username').value.trim();
    const oib = document.getElementById('org-staff-oib').value.trim();
    const password = document.getElementById('org-staff-password').value;
    const first_name = document.getElementById('org-staff-first').value.trim() || null;
    const last_name = document.getElementById('org-staff-last').value.trim() || null;
    const orgSelect = document.getElementById('org-staff-organization');
    const selectedOrgId = orgSelect && orgSelect.value
      ? Number(orgSelect.value)
      : Number(getActiveStaffOrganizationId() || (currentUser && currentUser.organization_id));
    if (!username || !oib || !password || !first_name || !last_name) {
      errEl.textContent = 'Sva polja su obavezna.';
      return;
    }
    if (password.length < 6) {
      errEl.textContent = 'Lozinka mora imati najmanje 6 znakova.';
      return;
    }
    if (oib.length !== 11 || !/^\d+$/.test(oib)) {
      errEl.textContent = 'OIB mora sadržavati točno 11 znamenki.';
      return;
    }
    if (!/^[a-zA-Z0-9]+$/.test(username)) {
      errEl.textContent = 'Korisničko ime smije sadržavati samo slova i brojeve.';
      return;
    }
    const res = await fetch('/auth/admins', {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ username, oib, password, first_name, last_name, organization_ids: selectedOrgId ? [selectedOrgId] : undefined }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      errEl.textContent = err.detail || 'Greška pri kreiranju admina.';
      return;
    }
    document.getElementById('org-staff-username').value = '';
    document.getElementById('org-staff-oib').value = '';
    document.getElementById('org-staff-password').value = '';
    document.getElementById('org-staff-first').value = '';
    document.getElementById('org-staff-last').value = '';
    showToast('Djelatnik je kreiran.');
    await loadOwnerAdmins();
    await loadOrganizationUsers();
  }

  async function ownerToggleAdmin(adminId, isActive) {
    const res = await fetch(`/auth/admins/${adminId}`, {
      method: 'PATCH',
      headers: authHeaders(),
      body: JSON.stringify({ is_active: isActive }),
    });
    if (!res.ok) {
      showToast('Greška pri promjeni statusa admina.');
      return;
    }
    await loadOwnerAdmins();
    await loadOrganizationUsers();
  }

  async function ownerDeleteAdmin(adminId) {
    if (!confirm('Jeste li sigurni da želite obrisati admin korisnika?')) return;
    const res = await fetch(`/auth/admins/${adminId}`, {
      method: 'DELETE',
      headers: authHeaders(),
    });
    if (!res.ok && res.status !== 204) {
      showToast('Greška pri brisanju admina.');
      return;
    }
    showToast('Admin korisnik je obrisan.');
    await loadOwnerAdmins();
    await loadOrganizationUsers();
  }

  //  ISSP INTEGRATION 

  function setISSPLinkMode(mode) {
    isspLinkMode = mode === 'qr' ? 'qr' : 'manual';
    const manualBtn = document.getElementById('issp-mode-manual-btn');
    const qrBtn = document.getElementById('issp-mode-qr-btn');
    const manualFields = document.getElementById('issp-manual-fields');
    const qrFields = document.getElementById('issp-qr-fields');
    if (manualBtn) manualBtn.classList.toggle('active', isspLinkMode === 'manual');
    if (qrBtn) qrBtn.classList.toggle('active', isspLinkMode === 'qr');
    if (manualFields) manualFields.style.display = isspLinkMode === 'manual' ? '' : 'none';
    if (qrFields) qrFields.style.display = isspLinkMode === 'qr' ? '' : 'none';
  }

  function setISSPButtonsLoading(loading, source) {
    const connectBtn = document.getElementById('issp-connect-btn');
    const syncBtn = document.getElementById('issp-sync-btn');
    if (connectBtn) {
      connectBtn.disabled = !!loading;
      connectBtn.textContent = loading && source === 'connect' ? 'Povezivanje...' : 'Poveži ISSP račun';
    }
    if (syncBtn) {
      syncBtn.disabled = !!loading;
      syncBtn.textContent = loading && source === 'sync' ? 'Osvježavanje...' : 'Osvježi ISSP podatke';
    }
  }

  function clearISSPQrPayload() {
    const payloadEl = document.getElementById('issp-qr-payload');
    const previewEl = document.getElementById('issp-qr-preview');
    const inputEl = document.getElementById('issp-qr-image-input');
    if (payloadEl) payloadEl.value = '';
    if (previewEl) previewEl.textContent = '';
    if (inputEl) inputEl.value = '';
  }

  async function onISSPQrImageSelected(event) {
    const input = event && event.target;
    const file = input && input.files ? input.files[0] : null;
    const errEl = document.getElementById('issp-error');
    const previewEl = document.getElementById('issp-qr-preview');
    if (errEl) errEl.textContent = '';
    if (previewEl) previewEl.textContent = '';
    if (!file) return;

    if (typeof BarcodeDetector === 'undefined') {
      if (errEl) errEl.textContent = 'Browser ne podržava očitavanje QR koda iz slike. Zalijepite payload ručno.';
      return;
    }

    try {
      const detector = new BarcodeDetector({ formats: ['qr_code'] });
      const bitmap = await createImageBitmap(file);
      const barcodes = await detector.detect(bitmap);
      if (typeof bitmap.close === 'function') bitmap.close();
      const qrPayload = barcodes && barcodes[0] && barcodes[0].rawValue ? String(barcodes[0].rawValue) : '';
      if (!qrPayload) {
        if (errEl) errEl.textContent = 'QR kod nije pronađen na odabranoj slici.';
        return;
      }
      const payloadEl = document.getElementById('issp-qr-payload');
      if (payloadEl) payloadEl.value = qrPayload;
      if (previewEl) previewEl.textContent = `QR payload učitan (${qrPayload.length} znakova).`;
    } catch {
      if (errEl) errEl.textContent = 'Neuspjelo očitavanje QR koda iz slike.';
    }
  }

  function renderISSPResult(data) {
    const resultEl = document.getElementById('issp-result');
    const resultContent = document.getElementById('issp-result-content');
    if (!resultEl || !resultContent) return;
    const normalized = normalizeISSPPayload(data);
    if (!normalized) {
      resultEl.style.display = 'none';
      resultContent.innerHTML = '';
      return;
    }
    resultEl.style.display = 'block';
    const fields = [
      ['Ime i prezime', normalized.full_name || '-'],
      ['Ime', normalized.first_name || '-'],
      ['Prezime', normalized.last_name || '-'],
      ['Fakultet', normalized.faculty || '-'],
      ['Broj iskaznice', normalized.card_number || '-'],
      ['ESI', normalized.esi || '-'],
      ['Preostale subvencije', normalized.subsidy_remaining != null ? fmt(Number(normalized.subsidy_remaining)) : '-'],
      ['Izvor podataka', normalized.source || 'ISSP'],
    ];
    resultContent.innerHTML = fields.map(([label, value]) => `
      <div class="profile-meta-item">
        <span class="profile-meta-label">${escapeHtml(label)}</span>
        <span class="profile-meta-value">${escapeHtml(value)}</span>
      </div>
    `).join('');
  }

  async function refreshCurrentUserFromBackend() {
    const meRes = await fetch('/auth/me', { headers: authHeaders() });
    if (!meRes.ok) return;
    currentUser = await meRes.json();
    hydrateISSPProfileFromStorage();
    syncAvatarUIFromCurrentUser();
  }

  async function connectISSPAccount() {
    const errEl = document.getElementById('issp-error');
    const resultEl = document.getElementById('issp-result');
    errEl.textContent = '';
    resultEl.style.display = 'none';
    setISSPButtonsLoading(true, 'connect');

    try {
      let payload = null;
      if (isspLinkMode === 'qr') {
        const qrPayload = (document.getElementById('issp-qr-payload').value || '').trim();
        if (!qrPayload) {
          errEl.textContent = 'Unesite ili učitajte QR payload.';
          return;
        }
        payload = { method: 'qr', qr_payload: qrPayload };
      } else {
        const cardNumber = (document.getElementById('issp-card-number').value || '').trim();
        const esi = (document.getElementById('issp-esi').value || '').trim();
        if (!cardNumber || !esi) {
          errEl.textContent = 'Unesite broj studentske iskaznice i ESI broj.';
          return;
        }
        payload = { method: 'manual', card_number: cardNumber, esi };
      }

      const res = await fetch('/students/issp/link', {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify(payload),
      });

      if (res.status === 503) {
        const err = await res.json().catch(() => ({}));
        errEl.textContent = err.message || 'ISSP servis nije konfiguriran na serveru. Obratite se administratoru.';
        isspEnabled = false;
        return;
      }

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        errEl.textContent = err.detail || err.message || 'Neuspjelo povezivanje ISSP računa.';
        return;
      }

      const data = await res.json();
      applyISSPDataToCurrentUser(data);
      renderISSPResult(data);
      await refreshCurrentUserFromBackend();
      await renderProfilePage();
      showToast('ISSP račun je uspješno povezan.');
    } catch {
      errEl.textContent = 'Greška pri spajanju na ISSP servis.';
    } finally {
      setISSPButtonsLoading(false, 'connect');
    }
  }

  async function syncISSPAccount() {
    const errEl = document.getElementById('issp-error');
    errEl.textContent = '';
    setISSPButtonsLoading(true, 'sync');
    try {
      const res = await fetch('/students/issp/sync', {
        method: 'POST',
        headers: authHeaders(),
      });
      if (res.status === 503) {
        const err = await res.json().catch(() => ({}));
        errEl.textContent = err.message || 'ISSP servis nije konfiguriran na serveru. Obratite se administratoru.';
        isspEnabled = false;
        return;
      }
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        errEl.textContent = err.detail || err.message || 'Neuspjelo osvježavanje ISSP podataka.';
        return;
      }
      const data = await res.json();
      applyISSPDataToCurrentUser(data);
      renderISSPResult(data);
      await refreshCurrentUserFromBackend();
      await renderProfilePage();
      showToast('ISSP podaci su osvježeni.');
    } catch {
      errEl.textContent = 'Greška pri spajanju na ISSP servis.';
    } finally {
      setISSPButtonsLoading(false, 'sync');
    }
  }

  // Check ISSP service status on app initialization
  async function checkISSPStatus() {
    try {
      const res = await fetch('/students/status', { headers: authHeaders() });
      if (res.ok) {
        const data = await res.json();
        isspEnabled = !!data.enabled;
      } else {
        isspEnabled = false;
      }
    } catch {
      isspEnabled = false;
    }
    setISSPLinkMode(isspLinkMode);
  }

  //  KEYBOARD 
  document.addEventListener('click', e => {
    if (organizationCityDropdownOpen) {
      const wrap = document.getElementById('org-city-filter-wrap');
      if (wrap && !wrap.contains(e.target)) {
        closeOrganizationCityDropdown();
      }
    }

    const mini = document.getElementById('mini-cart-popover');
    const trigger = document.getElementById('top-cart-wrap');
    if (mini && trigger && mini.style.display !== 'none' && !trigger.contains(e.target)) {
      closeMiniCart();
    }
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      closeOrganizationPickerModal();
      closeOrganizationEditModal();
      closeMiniCart();
      closeMobileSidebar();
    }
    if (e.key !== 'Enter') return;
    if (document.getElementById('login-page').style.display === 'none') return;
    if (document.getElementById('register-form').style.display !== 'none') doRegister();
    else doLogin();
  });

  //  BOOT 
  setLoginMode('student');
  (async () => { if (token) await initApp(); })();
