from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


DEFAULT_OUTPUT = Path("output/final_verified_av/CV_Analysis_Formulas_and_References.pdf")


def p(text: str, style):
    return Paragraph(text, style)


def formula(text: str, styles):
    return Paragraph(text.replace("\n", "<br/>"), styles["Formula"])


def ref_item(label: str, body: str, url: str, styles):
    return ListItem(
        Paragraph(
            f"<b>{label}</b> {body}<br/><link href='{url}' color='blue'>{url}</link>",
            styles["Body"],
        ),
        leftIndent=10,
    )


def build(output_path: str | Path = DEFAULT_OUTPUT) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="TitleCenter",
            parent=styles["Title"],
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=21,
            spaceAfter=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Body",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9.2,
            leading=12.2,
            spaceAfter=5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="H1",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            spaceBefore=9,
            spaceAfter=5,
        )
    )
    styles.add(
        ParagraphStyle(
            name="H2",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13,
            spaceBefore=7,
            spaceAfter=3,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Formula",
            parent=styles["Code"],
            fontName="Courier",
            fontSize=8.4,
            leading=11,
            leftIndent=8,
            rightIndent=8,
            backColor=colors.HexColor("#F7F7F7"),
            borderColor=colors.HexColor("#DDDDDD"),
            borderWidth=0.35,
            borderPadding=4,
            spaceBefore=3,
            spaceAfter=6,
        )
    )

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=1.55 * cm,
        leftMargin=1.55 * cm,
        topMargin=1.35 * cm,
        bottomMargin=1.35 * cm,
        title="CV Analysis Formulas and References",
        author="Codex",
    )

    story = []
    story.append(p("CV Analysis Formulas and References", styles["TitleCenter"]))
    story.append(
        p(
            "This document lists the formulas used in the verified AV.csv analysis pipeline. "
            "It describes what is computed from the supplied CSV and separates those calculations "
            "from analyses that require additional experimental files.",
            styles["Body"],
        )
    )

    scope_rows = [
        ["Item", "Status"],
        ["Input file", "AV.csv only"],
        ["Valid composition count", "One CSV source only; no true x=0, x=5%, x=10% comparison"],
        ["Final plot folder", "output/final_verified_av"],
        ["Verified tests", "pytest: 5 passed"],
        ["Audit checks", "Independent b-value, R2, Dunn k1/k2, and kernel checks matched exactly"],
    ]
    table = Table(scope_rows, colWidths=[4.0 * cm, 12.0 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E8EEF7")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#BBBBBB")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("LEADING", (0, 0), (-1, -1), 11),
            ]
        )
    )
    story.append(table)

    story.append(p("1. Data Loading and Branch Handling", styles["H1"]))
    story.append(
        p(
            "Cyclic voltammetry loops contain forward and reverse sweeps, so potentials repeat. "
            "The corrected loader preserves raw acquisition order for CV overlays and splits the loop "
            "into monotonic branches for potential-resolved kinetic analysis.",
            styles["Body"],
        )
    )
    formula(
        "Raw CV data: I_raw[t, j] at potential V_raw[t], scan rate v_j\n"
        "Branch selection: choose monotonic forward branch for kinetic fits\n"
        "Uniform grid: V_i = linspace(V_min, V_max, N)\n"
        "Interpolated branch current: I(V_i, v_j) = interp(V_i; V_branch, I_branch[:, j])",
        styles,
    )

    story.append(p("2. CV Overlay", styles["H1"]))
    story.append(p("The overlay is the raw loop, not the sorted branch.", styles["Body"]))
    formula("x-axis = V_raw[t]\ny-axis = I_raw[t, v_j]\none curve per scan rate v_j", styles)

    story.append(p("3. Absolute-Current Heatmap", styles["H1"]))
    formula("Heatmap color at potential V_i and scan rate v_j:\nH_ij = |I(V_i, v_j)|", styles)

    story.append(p("4. Peak Current Scaling", styles["H1"]))
    story.append(
        p(
            "Peak scaling checks whether peak current follows a square-root scan-rate trend, "
            "as expected for diffusion-influenced faradaic peaks.",
            styles["Body"],
        )
    )
    formula(
        "Anodic peak at v_j:     I_a,peak(v_j) = max_i I(V_i, v_j)\n"
        "Cathodic peak at v_j:   I_c,peak(v_j) = min_i I(V_i, v_j)\n"
        "Regression variable:    x_j = sqrt(v_j)\n"
        "Linear model:           |I_peak(v_j)| = m x_j + c\n"
        "Coefficient of determination:\n"
        "R2 = 1 - sum_j (y_j - yhat_j)^2 / sum_j (y_j - mean(y))^2",
        styles,
    )

    story.append(p("5. b-Value Analysis", styles["H1"]))
    story.append(
        p(
            "The b-value is computed pointwise at each potential from a log-log power law between "
            "current magnitude and scan rate.",
            styles["Body"],
        )
    )
    formula(
        "Power law:        |i(V, v)| = a(V) v^b(V)\n"
        "Linearized form:  log |i(V, v)| = log a(V) + b(V) log v\n"
        "At each V_i:      b(V_i) = slope of log |I(V_i, v_j)| vs log v_j\n"
        "Interpretation:   b ~ 0.5 diffusion-influenced; b ~ 1.0 surface/capacitive",
        styles,
    )

    story.append(p("6. Dunn Capacitive/Diffusion Decomposition", styles["H1"]))
    story.append(
        p(
            "Dunn analysis separates current at each potential into a term proportional to scan rate "
            "and a term proportional to square-root scan rate.",
            styles["Body"],
        )
    )
    formula(
        "Model:                 i(V, v) = k1(V) v + k2(V) sqrt(v)\n"
        "Linearized fitting:    i(V, v) / sqrt(v) = k1(V) sqrt(v) + k2(V)\n"
        "Capacitive current:    i_cap(V, v) = k1(V) v\n"
        "Diffusion current:     i_diff(V, v) = k2(V) sqrt(v)\n"
        "Capacitive fraction:   F_cap(v) = integral |i_cap(V, v)| dV /\n"
        "                         [integral |i_cap(V, v)| dV + integral |i_diff(V, v)| dV]\n"
        "Diffusion fraction:    F_diff(v) = 1 - F_cap(v)",
        styles,
    )

    story.append(p("7. Threshold Kinetic Regime Map", styles["H1"]))
    formula(
        "DD if b(V_i) <= 0.6\n"
        "CD if b(V_i) >= 0.7\n"
        "mixed otherwise\n\n"
        "DD = diffusion-influenced\nCD = capacitive-dominated",
        styles,
    )

    story.append(p("8. Ising/QUBO-Style Segmentation", styles["H1"]))
    story.append(
        p(
            "This is an algorithmic regularization layer. It should be interpreted alongside b-value "
            "and Dunn maps, not as independent physical proof.",
            styles["Body"],
        )
    )
    formula(
        "State: s_i in {0, 1}\n"
        "0 = DD, 1 = CD\n\n"
        "Local diffusion cost:    C_DD(i) = [b_i - 0.5]^2\n"
        "Local capacitive cost:   C_CD(i) = [b_i - 1.0]^2\n\n"
        "Regularized objective:\n"
        "E(s) = sum_i C_i(s_i) + lambda sum_i 1[s_i != s_(i-1)]\n\n"
        "Current implementation: lambda = 0.18\n"
        "Optimization method: dynamic programming over the one-dimensional potential axis",
        styles,
    )

    story.append(PageBreak())
    story.append(p("9. Quantum-Kernel PCA", styles["H1"]))
    story.append(
        p(
            "The final corrected implementation uses an explicit angle-encoded fidelity kernel. "
            "Each scan-rate CV curve is converted to normalized shape features, then mapped to "
            "a product Ry feature state. Kernel PCA is performed on the centered Gram matrix.",
            styles["Body"],
        )
    )
    formula(
        "Curve feature vector for scan rate v_j: x_j = normalized CV-shape vector\n\n"
        "Angle-encoding feature map:\n"
        "|phi(x)> = tensor_k Ry(x_k) |0>\n\n"
        "Fidelity kernel:\n"
        "K_ij = |<phi(x_i) | phi(x_j)>|^2\n\n"
        "For product Ry encoding used here:\n"
        "K_ij = product_k cos^2((x_ik - x_jk) / 2)\n\n"
        "Kernel centering:\n"
        "K_c = K - 1_N K - K 1_N + 1_N K 1_N\n"
        "where 1_N is the N x N matrix with every entry 1/N\n\n"
        "Eigenproblem:\n"
        "K_c u_l = lambda_l u_l\n\n"
        "KPCA coordinate:\n"
        "score_il = sqrt(lambda_l) u_il\n\n"
        "Explained variance:\n"
        "EV_l = lambda_l / sum_j lambda_j",
        styles,
    )

    story.append(p("10. Classical PCA", styles["H1"]))
    story.append(p("Classical PCA remains available for diagnostic output, but the quantum-kernel figure uses Section 9.", styles["Body"]))
    formula(
        "Standardization: X_scaled = (X - mean(X)) / std(X)\n"
        "SVD form:        X_scaled = U Sigma V^T\n"
        "Scores:          scores = U Sigma\n"
        "Explained variance ratio: eigenvalue_l / sum_j eigenvalue_j",
        styles,
    )

    story.append(p("11. Analyses Not Computable from AV.csv Alone", styles["H1"]))
    story.append(
        p(
            "The following reference-PDF analyses require additional raw data files and are not derived "
            "from AV.csv: true x=0/5/10 composition comparison, GCD/R2WLD, EIS, XRD, TEM, and Raman.",
            styles["Body"],
        )
    )

    story.append(p("References", styles["H1"]))
    refs = [
        ref_item(
            "[1]",
            "J. Wang, J. Polleux, J. Lim, B. Dunn, Pseudocapacitive contributions to electrochemical energy storage in TiO2 (anatase) nanoparticles, J. Phys. Chem. C 111, 14925-14931 (2007). DOI: 10.1021/jp074464w.",
            "https://doi.org/10.1021/jp074464w",
            styles,
        ),
        ref_item(
            "[2]",
            "V. Augustyn, P. Simon, B. Dunn, Pseudocapacitive oxide materials for high-rate electrochemical energy storage, Energy Environ. Sci. 7, 1597-1614 (2014). DOI: 10.1039/C3EE44164D.",
            "https://doi.org/10.1039/C3EE44164D",
            styles,
        ),
        ref_item(
            "[3]",
            "B. Schoelkopf, A. Smola, K.-R. Mueller, Nonlinear component analysis as a kernel eigenvalue problem, Neural Computation 10, 1299-1319 (1998). DOI: 10.1162/089976698300017467.",
            "https://doi.org/10.1162/089976698300017467",
            styles,
        ),
        ref_item(
            "[4]",
            "V. Havlicek, A. D. Corcoles, K. Temme, et al., Supervised learning with quantum-enhanced feature spaces, Nature 567, 209-212 (2019). DOI: 10.1038/s41586-019-0980-2.",
            "https://doi.org/10.1038/s41586-019-0980-2",
            styles,
        ),
        ref_item(
            "[5]",
            "M. Schuld, Supervised quantum machine learning models are kernel methods, arXiv:2101.11020 (2021).",
            "https://arxiv.org/abs/2101.11020",
            styles,
        ),
        ref_item(
            "[6]",
            "A. Lucas, Ising formulations of many NP problems, Frontiers in Physics 2, Article 5 (2014). DOI: 10.3389/fphy.2014.00005.",
            "https://doi.org/10.3389/fphy.2014.00005",
            styles,
        ),
        ref_item(
            "[7]",
            "Nanoscale review discussion of Dunn-style CV separation: i(V) = k1 v + k2 v^(1/2), and i(V)/v^(1/2) = k1 v^(1/2) + k2.",
            "https://doi.org/10.1039/C9NR05732C",
            styles,
        ),
    ]
    story.append(ListFlowable(refs, bulletType="bullet", leftIndent=12))

    story.append(Spacer(1, 8))
    story.append(
        p(
            "Generated from the corrected local pipeline. This PDF documents formulas only; numerical audit files are in output/final_verified_av/audit/.",
            styles["Body"],
        )
    )

    doc.build(story)
    return output_path


if __name__ == "__main__":
    print(build())
