document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("matchForm");
    const loadingOverlay = document.getElementById("loadingOverlay");

    if (form) {
        form.addEventListener("submit", () => {
            if (loadingOverlay) {
                loadingOverlay.classList.add("show");
            }
        });
    }

    // Application Modal Handler
    const applyButtons = document.querySelectorAll(".btn-apply");
    const applicationModal = new bootstrap.Modal(document.getElementById("applicationModal"));
    const submitBtn = document.getElementById("submitApplication");

    applyButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const jobTitle = btn.getAttribute("data-job-title");
            const jobCompany = btn.getAttribute("data-job-company");
            
            document.getElementById("modalJobTitle").value = jobTitle;
            document.getElementById("modalJobCompany").value = jobCompany;
            
            applicationModal.show();
        });
    });

    submitBtn.addEventListener("click", () => {
        const name = document.querySelector("input[placeholder='Your full name']").value;
        const email = document.querySelector("input[placeholder='your.email@example.com']").value;
        const phone = document.querySelector("input[placeholder='+91 9876543210']").value;

        if (!name || !email || !phone) {
            alert("❌ Please fill all required fields!");
            return;
        }

        alert(`✅ Application submitted successfully!\n\nWe'll contact you at ${email} soon.`);
        applicationModal.hide();
        
        // Reset form
        document.querySelectorAll("#applicationModal .form-control").forEach(input => {
            input.value = "";
        });
    });

    const filterButtons = document.querySelectorAll(".filter-chip");
    const jobCards = document.querySelectorAll(".job-card");

    function applyFilter(filter) {
        jobCards.forEach(card => {
            const categories = (card.getAttribute("data-categories") || "").split(",");
            const show = filter === "all" || categories.includes(filter);
            card.style.display = show ? "block" : "none";
        });
    }

    filterButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            filterButtons.forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            applyFilter(btn.getAttribute("data-filter"));
        });
    });

    applyFilter("all");
});