struct FittedStem {
    double slope;
    double intercept;
    double width;
};

std::optional<FittedStem> measureStraightStem(const std::vector<StemSection> &track, double slope, bool retry)
{
    if (track.size()<13)
        return std::nullopt;
    double sumY=0, sumX=0, sumYY=0, sumXY=0;
    std::vector<double> widths;
    for (const auto &p: track) {
        sumY+=p.y+.5;
        sumX+=p.center;
        sumYY+=(p.y+.5)*(p.y+.5);
        sumXY+=(p.y+.5)*p.center;
        widths.push_back(p.mass/255);
    }
    const double n=track.size();
    const double fit=(sumXY-sumX*sumY/n)/(sumYY-sumY*sumY/n);
    if (std::abs(fit-slope)>.105)
        return std::nullopt;
    const double intercept=(sumX-fit*sumY)/n;
    double squared=0;
    for (const auto &p: track) {
        const double error=p.center-intercept-fit*(p.y+.5);
        squared+=error*error;
    }
    std::sort(widths.begin(),widths.end());
    if (squared/n>(retry ? .125 : .115) || widths[widths.size()*3/4]-widths[widths.size()/4]>1.08)
        return std::nullopt;
    return FittedStem{fit,intercept,widths[widths.size()/2]};
}

void alignStraightStem(const std::vector<StemSection> &track, FittedStem fit,
                       std::vector<fontreal_v3::Coverage> &values,
                       const fontreal_v3::OutlineSamples &original, fontreal_v3::OutlineSamples &samples,
                       fontreal_v3::Ink ink, QByteArray &selected, int mode, QByteArray *savedJoins, std::optional<double> guideSlope)
{
    using namespace fontreal_v3;
    if (guideSlope) {
        const double middle=(track.front().y+track.back().y+1.)/2;
        const double blended=.82*(*guideSlope)+.18*fit.slope;
        fit.intercept+=(fit.slope-blended)*middle;
        fit.slope=blended;
    }
    const int width=samples.frame.width, pad=(samples.pitch-4*width)/2;
    const auto overlap=[](double first, double last, int column) {
        return std::max(0.,std::min(last,column+1.)-std::max(first,double(column)));
    };
    struct StrokeRow {
        int y, left, right;
        double density;
        bool touchesJunction;
    };
    std::vector<StrokeRow> rows;
    std::vector<double> densities;
    for (int y=(track.front().y+3)/4; y<=(track.back().y-3)/4; ++y) {
        const double center=fit.intercept+fit.slope*(4*y+2);
        const int left=std::max(0,int(std::floor((center-fit.width/2-.78)/4)));
        const int right=std::min(width,int(std::ceil((center+fit.width/2+.78)/4)));
        if (left>=right)
            continue;
        bool touchesJunction=false;
        double density=0;
        for (int x=left; x<right; ++x) {
            if (selected[y*width+x])
                touchesJunction=true;
            density+=linearInk(values[y*width+x],ink);
        }
        rows.push_back({y,left,right,density,touchesJunction});
        if (!touchesJunction)
            densities.push_back(density);
    }
    if (densities.size()<3)
        return;
    std::sort(densities.begin(),densities.end());
    const double typical=densities[densities.size()/2];
    for (const auto &row: rows) {
        if (row.touchesJunction || row.density>typical*1.33 || row.density<typical*.64)
            continue;
        const int y=row.y;
        std::array<double,4> first{},last{};
        for (int i=0;i<4;++i) {
            const double center=fit.intercept+fit.slope*(y*4+i+.5);
            // Preserve the local stroke width and cap center shifts at one tenth of a device pixel.
            const auto &section=track[y*4+i-track.front().y];
            const double maxMove=.40;
            const double placed=section.center+std::clamp(center-section.center,-maxMove,maxMove);
            const double extent=(.72*fit.width+.28*section.mass/255)/2;
            first[i]=placed-extent;
            last[i]=placed+extent;
        }
        if (savedJoins) {
            std::vector<double> loss(row.right-row.left);
            double removed=0, added=0;
            for(int x=row.left;x<row.right;++x) {
                for(int i=0;i<4;++i) {
                    for(int sx=4*x;sx<4*x+4;++sx) {
                        const double support=original.highPixel(sx,4*y+i)/255.;
                        const double proposed=overlap(first[i],last[i],sx);
                        const double missing=std::max(0.,support-proposed);
                        added+=std::max(0.,proposed-support);
                        loss[x-row.left]+=missing;
                        removed+=missing;
                    }
                }
            }
            // A line fit must leave the branch of a joining stroke intact.
            const bool rigidShift=guideSlope && removed<added+.42 && removed<3.65;
            if (!rigidShift && removed>1.80 && *std::max_element(loss.begin(),loss.end())>1.24) {
                for(int x=row.left;x<row.right;++x) {
                    if (loss[x-row.left]>1.18 && original.center(x,y)>=39)
                        (*savedJoins)[y*width+x]=char(255);
                }
                continue;
            }
        }
        std::vector<double> areas;
        double total=0;
        for (int x=row.left;x<row.right;++x) {
            double area=0;
            for (int i=0;i<4;++i) {
                for (int sx=4*x;sx<4*x+4;++sx) {
                    const double value=overlap(first[i],last[i],sx);
                    area+=value;
                    const auto old=original.highPixel(sx,4*y+i);
                    if (old || value)
                        samples.pixels[(4*y+i+pad)*samples.pitch+sx+pad]=std::lround(value*255);
                }
            }
            const double weighted=mode==6 ? std::pow(area,1.32) : area;
            total+=weighted;
            areas.push_back(weighted);
        }
        if (total<=0.)
            continue;
        double density=.8*typical+.2*row.density;
        if (mode>=7) {
            const double native=total/16;
            const double limit=ink==Ink::Light ? (mode>=9 ? .87*native+.025 : .99*native+.035) : 1.33*native+.025;
            density=std::min(density,limit);
        }
        if (guideSlope) {
            const double center=(fit.intercept+fit.slope*(4*y+2))/4-.5;
            double adjusted=0;
            for (int x=row.left;x<row.right;++x) {
                auto &area=areas[x-row.left];
                const double phase=std::max(0.,1.-std::abs(x-center));
                const double edge=std::max(original.blockSum(x,y,-2,0),original.blockSum(x,y,2,0))/4080.;
                if(area>0. || edge>.045)
                    area=.50*area+.50*phase*total;
                adjusted+=area;
            }
            total=adjusted;
        }
        for (int x=row.left;x<row.right;++x) {
            const int index=y*width+x;
            values[index]=encodedInk(std::min(.987,density*areas[x-row.left]/total),ink);
            selected[index]=char(255);
        }
    }
}
