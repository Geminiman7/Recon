async function registerCompany() {

    try {

        const response = await api(
            "/auth/register",
            "POST",
            {
                company_name: company_name.value,
                company_email: company_email.value,
                phone: phone.value,
                address: address.value,
                admin_name: admin_name.value,
                admin_email: admin_email.value,
                password: password.value
            }
        );

        alert(response.message);

        window.location.href = "login.html";

    } catch (error) {

        alert(error.message);

    }

}