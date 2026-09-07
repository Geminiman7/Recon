const message = document.getElementById("formMessage");

document.getElementById("forgotPasswordForm")?.addEventListener("submit", async event => {
    event.preventDefault();
    message.textContent = "Sending reset link…";
    try {
        const response = await api("/auth/forgot-password", "POST", { email: document.getElementById("email").value });
        message.textContent = response.message;
        if (response.reset_url) {
            const link = document.createElement("a");
            link.href = response.reset_url;
            link.textContent = "Open development reset link";
            message.append(document.createElement("br"), link);
        }
    } catch (error) {
        message.textContent = error.message;
    }
});

document.getElementById("resetPasswordForm")?.addEventListener("submit", async event => {
    event.preventDefault();
    const password = document.getElementById("password").value;
    if (password !== document.getElementById("confirmPassword").value) {
        message.textContent = "The passwords do not match.";
        return;
    }
    const token = new URLSearchParams(window.location.search).get("token");
    if (!token) {
        message.textContent = "This reset link is invalid.";
        return;
    }
    try {
        const response = await api("/auth/reset-password", "POST", { token, password });
        message.textContent = response.message;
        setTimeout(() => { window.location.href = "login.html"; }, 1200);
    } catch (error) {
        message.textContent = error.message;
    }
});
