async function logout() {
    try {
        await api("/auth/logout", "POST");
        location.replace("login.html");
    } catch (error) {
        if (error.status === 401) location.replace("login.html");
        else alert(error.message);
    }
}

async function protectPage() {
    try {
        await api("/auth/me");
    } catch (error) {
        if (error.status !== 401) alert(error.message);
    }
}
